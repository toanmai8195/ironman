package com.tm.starrockbitmap;

import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import org.roaringbitmap.RoaringBitmap;

/** Phần làm việc với StarRocks: schema, sinh data gold, kéo tag về service. */
final class Sr {
  private Sr() {}

  /** Điều kiện tag đang gắn với actor (bỏ các dòng REMOVE). */
  static final String ACTIVE = "attribute_id = ? AND tag_id = ? AND latest_signal = 1";

  private static final String[] DDL = {
    "CREATE DATABASE IF NOT EXISTS bm_bench",
    // pipeline B: tag bitmap native
    "CREATE TABLE IF NOT EXISTS bm_bench.tag_bitmap (tag_id INT NOT NULL, bm BITMAP BITMAP_UNION NOT NULL)"
        + " AGGREGATE KEY(tag_id) DISTRIBUTED BY HASH(tag_id) BUCKETS 8"
        + " PROPERTIES(\"replication_num\"=\"1\")",
    // pipeline B: segment bitmap native
    "CREATE TABLE IF NOT EXISTS bm_bench.segment_bitmap (segment_id INT NOT NULL, bm BITMAP BITMAP_UNION NOT NULL)"
        + " AGGREGATE KEY(segment_id) DISTRIBUTED BY HASH(segment_id) BUCKETS 8"
        + " PROPERTIES(\"replication_num\"=\"1\")",
  };

  /** DDL bảng gold. Native: bảng SR; Iceberg: tạo qua external catalog (Iceberg không có SMALLINT). */
  private static String goldDdl(Config cfg) {
    // giống iceberg_catalog_hms.cdp.aggregating_tag_not_mutex_most_recent của core-service
    // (1 dòng / (attribute, actor, tag); latest_signal 1 = ADD, -1 = REMOVE). Nguồn cho cả 2 pipeline.
    if (cfg.goldInIceberg()) {
      return "CREATE TABLE IF NOT EXISTS " + cfg.goldTable() + " (attribute_id INT, actor_id INT, tag_id INT,"
          + " latest_signal INT, last_persist_time DATETIME)";
    }
    return "CREATE TABLE IF NOT EXISTS " + cfg.goldTable() + " ("
        + "attribute_id INT NOT NULL, actor_id INT NOT NULL, tag_id INT NOT NULL,"
        + " latest_signal SMALLINT NOT NULL, last_persist_time DATETIME NOT NULL)"
        + " DUPLICATE KEY(attribute_id, actor_id, tag_id) DISTRIBUTED BY HASH(actor_id) BUCKETS 32"
        + " PROPERTIES(\"replication_num\"=\"1\")";
  }

  static void load(Connection c, Config cfg, Stats st) throws Exception {
    try (Statement s = c.createStatement()) {
      for (String q : DDL) {
        s.execute(q);
      }
      if (cfg.goldInIceberg()) {
        s.execute("CREATE DATABASE IF NOT EXISTS " + cfg.goldCatalog() + ".bm_bench");
        s.execute("DROP TABLE IF EXISTS " + cfg.goldTable());
        s.execute(goldDdl(cfg));
      } else {
        s.execute(goldDdl(cfg));
        s.execute("TRUNCATE TABLE " + cfg.goldTable());
      }
      // Sinh data ngay trong SR (không kéo qua mạng). Với h = hash(u, t) % 10000:
      //   h < pct*100                      -> signal  1 (ADD, thành viên tag)
      //   pct*100 <= h < (pct+removed)*100 -> signal -1 (REMOVE, phải bị loại khi build bitmap)
      for (int t = 1; t <= cfg.tags(); t++) {
        int pct = cfg.tagPct(t); // rải min..max, xác định theo t
        String q =
            String.format(
                "INSERT INTO %s SELECT %d, CAST(generate_series AS INT), %d,"
                    + " IF(h < %d, 1, -1), seconds_add('2026-01-01 00:00:00', h %% 86400)"
                    + " FROM (SELECT generate_series, abs(murmur_hash3_32(generate_series, %d)) %% 10000 AS h"
                    + " FROM TABLE(generate_series(1, %d))) x WHERE h < %d",
                cfg.goldTable(), cfg.attributeOf(t), t, pct * 100, t, cfg.universe(), (pct + cfg.removedPct()) * 100);
        st.time("load gold / tag", () -> s.execute(q));
      }
      try (ResultSet rs = s.executeQuery("SELECT count(*) FROM " + cfg.goldTable())) {
        rs.next();
        long n = rs.getLong(1);
        System.out.printf("gold rows: %d (avg %d user/tag)%n", n, n / cfg.tags());
      }
    }
  }

  /** Kéo bitmap của 1 tag từ bảng gold về service (pipeline A, bước SR -> bitmap). */
  static RoaringBitmap fetchTag(Connection c, Config cfg, int attribute, int tag, Stats st) throws Exception {
    switch (cfg.export()) {
      case "agg":
        {
          // SR tự gom bitmap, chỉ ship 1 blob base64 về.
          String b64 =
              st.time(
                  "A1a SR agg+ship",
                  () -> {
                    try (PreparedStatement ps =
                        c.prepareStatement(
                            "SELECT bitmap_to_base64(bitmap_agg(actor_id))"
                                + " FROM " + cfg.goldTable() + " WHERE " + ACTIVE)) {
                      ps.setInt(1, attribute);
                      ps.setInt(2, tag);
                      try (ResultSet rs = ps.executeQuery()) {
                        rs.next();
                        return rs.getString(1);
                      }
                    }
                  });
          return st.time("A1b decode SR bitmap", () -> BitmapCodec.decodeStarRocks(b64));
        }
      case "rows":
        // Kéo từng user_id về rồi build bitmap ở service.
        return st.time("A1 SR scan rows+build", () -> scanRows(c, cfg, attribute, tag));
      default:
        throw new IllegalArgumentException("export mode không hợp lệ: " + cfg.export());
    }
  }

  private static RoaringBitmap scanRows(Connection c, Config cfg, int attribute, int tag) throws SQLException {
    RoaringBitmap bm = new RoaringBitmap();
    try (PreparedStatement ps =
        c.prepareStatement(
            "SELECT actor_id FROM " + cfg.goldTable() + " WHERE " + ACTIVE,
            ResultSet.TYPE_FORWARD_ONLY,
            ResultSet.CONCUR_READ_ONLY)) {
      ps.setFetchSize(Integer.MIN_VALUE); // streaming, không load hết vào memory
      ps.setInt(1, attribute);
      ps.setInt(2, tag);
      int[] buf = new int[1 << 16];
      int n = 0;
      try (ResultSet rs = ps.executeQuery()) {
        while (rs.next()) {
          buf[n++] = rs.getInt(1);
          if (n == buf.length) {
            bm.addN(buf, 0, n);
            n = 0;
          }
        }
      }
      bm.addN(buf, 0, n);
    }
    return bm;
  }

  /** Kích thước (byte) của bitmap SR khi serialize: độ dài base64 của bitmap_to_base64 giải ngược về byte. */
  static long bitmapBytes(Connection c, String selectBm) throws Exception {
    String q = selectBm.replaceFirst("SELECT bm", "SELECT length(bitmap_to_base64(bm))");
    try (var stmt = c.createStatement(); var rs = stmt.executeQuery(q)) {
      if (!rs.next()) return 0;
      long len = rs.getLong(1);
      return len / 4 * 3;
    }
  }
}
