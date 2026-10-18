package com.tm.starrockbitmap;

import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Random;
import org.roaringbitmap.RoaringBitmap;

/**
 * Các bước đo: etl (gold -> bitmap tag), segment (tính + lưu segment), getAll (lấy toàn bộ user của
 * segment). Pipeline A = bitmap lưu thành chunk trong Mongo, tính ở service; pipeline B = bitmap
 * native của StarRocks, tính trong SR.
 */
final class Bench {
  private Bench() {}

  /** Test 1, 2: từ lúc bắt đầu đọc gold đến khi bitmap tag đã lưu xong (Mongo hoặc bảng bitmap của SR). */
  static void etl(Connection c, MongoStore mg, Config cfg, Stats st) throws Exception {
    long sizeTotal = 0;
    for (int t = 1; t <= cfg.tags(); t++) {
      final int tag = t;
      long card = -1;
      long blobLen = 0;
      if (cfg.runA()) {
        // A: gold -> service -> bitmap -> các chunk trong Mongo
        RoaringBitmap bm = st.time("A1 total: SR -> bitmap", () -> Sr.fetchTag(c, cfg, cfg.attributeOf(tag), tag, st));
        byte[] blob = st.time("A2 serialize", () -> BitmapCodec.serialize(bm));
        st.time("A3 mongo put chunks (<=8MB, <=10 parallel)", () -> mg.put(MongoStore.tagKey(tag), blob));
        st.add("A tag total: gold -> mongo",
            st.last("A1 total: SR -> bitmap") + st.last("A2 serialize") + st.last("A3 mongo put chunks (<=8MB, <=10 parallel)"));
        card = bm.getLongCardinality();
        blobLen = blob.length;
        sizeTotal += blobLen;
        st.size("tag", "A", tag, blobLen);
      }
      if (cfg.runB()) {
        // B: gold -> bitmap native, toàn bộ trong SR
        try (PreparedStatement del = c.prepareStatement("DELETE FROM bm_bench.tag_bitmap WHERE tag_id = ?")) {
          del.setInt(1, tag);
          del.execute();
        }
        st.time("B1 SR gold -> tag_bitmap", () -> {
          try (PreparedStatement ps = c.prepareStatement(
              "INSERT INTO bm_bench.tag_bitmap SELECT tag_id, bitmap_agg(actor_id)"
                  + " FROM " + cfg.goldTable() + " WHERE " + Sr.ACTIVE + " GROUP BY tag_id")) {
            ps.setInt(1, cfg.attributeOf(tag));
            ps.setInt(2, tag);
            return ps.execute();
          }
        });
        st.add("B tag total: gold -> sr", st.last("B1 SR gold -> tag_bitmap"));
        st.size("tag", "B", tag, Sr.bitmapBytes(c, "SELECT bm FROM bm_bench.tag_bitmap WHERE tag_id = " + tag));
      }
      System.out.printf("etl tag %d/%d card=%d blob=%.2fMB%n", t, cfg.tags(), card, blobLen / 1e6);
    }
    System.out.printf("avg mongo blob/tag: %.2fMB%n", sizeTotal / (double) cfg.tags() / 1e6);
  }

  /**
   * Test 3: từ lúc bắt đầu lấy bitmap tag (Mongo hoặc SR) đến khi segment đã lưu xong. Mỗi segment là
   * and/or/not của 10 tag bất kỳ, kích thước kết quả nằm trong [seg-min, seg-max] universe.
   */
  static void segment(Connection c, MongoStore mg, Config cfg, Stats st) throws Exception {
    Random rng = new Random(cfg.seed());
    for (int s = 1; s <= cfg.segments(); s++) {
      final int seg = s;
      SegmentExpr expr = SegmentExpr.randomInRange(rng, cfg.tags(), cfg.leaves(), cfg::tagPctFraction, cfg.segMin(), cfg.segMax());
      long cardA = -1;
      long cardB = -1;
      long bytes = 0;

      if (cfg.runA()) {
        // ---- A: tải blob (các chunk) của 10 tag từ Mongo, tối đa 10 chunk song song -> and/or/not ở service -> ghi chunk
        List<Integer> tags = expr.tagIds();
        List<String> names = new ArrayList<>();
        for (int t : tags) {
          names.add(MongoStore.tagKey(t));
        }
        Map<String, byte[]> raw = st.time("A4 fetch tag chunks (<=10 parallel)", () -> mg.get(names));
        RoaringBitmap result = st.time("A5 deserialize + and/or/not", () -> {
          Map<Integer, RoaringBitmap> leaf = new HashMap<>();
          for (int t : tags) {
            leaf.put(t, BitmapCodec.deserialize(raw.get(MongoStore.tagKey(t))));
          }
          return expr.eval(leaf);
        });
        byte[] blob = st.time("A6 serialize", () -> BitmapCodec.serialize(result));
        st.time("A7 mongo put chunks (<=8MB, <=10 parallel)", () -> mg.put(MongoStore.segmentKey(seg), blob));
        st.add("A total (fetch+compute+store)",
            st.last("A4 fetch tag chunks (<=10 parallel)") + st.last("A5 deserialize + and/or/not")
                + st.last("A6 serialize") + st.last("A7 mongo put chunks (<=8MB, <=10 parallel)"));
        cardA = result.getLongCardinality();
        bytes = blob.length;
        st.size("segment", "A", seg, bytes);
        st.note("segment_users_a", cardA);
      }

      if (cfg.runB()) {
        // ---- B: toàn bộ trong SR
        try (PreparedStatement del = c.prepareStatement("DELETE FROM bm_bench.segment_bitmap WHERE segment_id = ?")) {
          del.setInt(1, seg);
          del.execute();
        }
        String sql = expr.insertSql(seg);
        st.time("B total: SQL compute + store", () -> {
          try (var stmt = c.createStatement()) {
            return stmt.execute(sql);
          }
        });
        try (PreparedStatement ps = c.prepareStatement("SELECT bitmap_count(bm) FROM bm_bench.segment_bitmap WHERE segment_id = ?")) {
          ps.setInt(1, seg);
          try (ResultSet rs = ps.executeQuery()) {
            rs.next();
            cardB = rs.getLong(1);
          }
        }
        st.size("segment", "B", seg, Sr.bitmapBytes(c, "SELECT bm FROM bm_bench.segment_bitmap WHERE segment_id = " + seg));
        st.note("segment_users_b", cardB);
        if (cfg.exportToMongo()) {
          // ---- Test 5 (kiến trúc lai): sao chép segment từ SR sang Mongo để phục vụ lấy toàn bộ user
          String b64 = st.time("B2 export: SR bitmap_to_base64", () -> {
            try (PreparedStatement ps = c.prepareStatement("SELECT bitmap_to_base64(bm) FROM bm_bench.segment_bitmap WHERE segment_id = ?")) {
              ps.setInt(1, seg);
              try (ResultSet rs = ps.executeQuery()) {
                rs.next();
                return rs.getString(1);
              }
            }
          });
          RoaringBitmap exported = st.time("B3 export: decode SR bitmap", () -> BitmapCodec.decodeStarRocks(b64));
          byte[] eb = st.time("B4 export: serialize", () -> BitmapCodec.serialize(exported));
          st.time("B5 export: mongo put chunks (<=8MB, <=10 parallel)", () -> mg.put(MongoStore.segmentKey(seg), eb));
          st.add("B hybrid total: SR compute + export to mongo",
              st.last("B total: SQL compute + store") + st.last("B2 export: SR bitmap_to_base64") + st.last("B3 export: decode SR bitmap")
                  + st.last("B4 export: serialize") + st.last("B5 export: mongo put chunks (<=8MB, <=10 parallel)"));
          st.note("segment_exported_users", exported.getLongCardinality());
        }
      }
      System.out.printf("segment %d card A=%d B=%d blob=%.2fMB  %s%n", seg, cardA, cardB, bytes / 1e6, expr);
    }
  }

  /** Test 4: từ lúc bắt đầu get đến khi service có toàn bộ user của segment. */
  static void getAll(Connection c, MongoStore mg, Config cfg, Stats st) throws Exception {
    Random rng = new Random(cfg.seed() + 2);
    for (int i = 0; i < cfg.fullGets(); i++) {
      int seg = 1 + rng.nextInt(cfg.segments());
      long a = -1;
      long b = -1;
      if (cfg.runA()) {
        a = st.time("A get all users: mongo get chunks + iterate", () -> {
          byte[] raw = mg.get(List.of(MongoStore.segmentKey(seg))).get(MongoStore.segmentKey(seg));
          long n = 0;
          var it = BitmapCodec.deserialize(raw).getIntIterator();
          while (it.hasNext()) {
            it.next();
            n++;
          }
          return n;
        });
        st.note("users_read_a", a);
      }
      if (cfg.runB()) {
        b = st.time("B get all users: SQL unnest", () -> {
          try (var stmt = c.createStatement()) {
            stmt.setFetchSize(Integer.MIN_VALUE);
            long n = 0;
            try (ResultSet rs = stmt.executeQuery("SELECT u FROM bm_bench.segment_bitmap, unnest(bitmap_to_array(bm)) AS t(u)"
                + " WHERE segment_id = " + seg)) {
              while (rs.next()) {
                rs.getLong(1);
                n++;
              }
            }
            return n;
          }
        });
        st.note("users_read_b", b);
      }
      System.out.printf("getall %d/%d segment=%d users A=%d B=%d%n", i + 1, cfg.fullGets(), seg, a, b);
    }
  }

  /** Nạp bitmap 1 tag từ SR về service (bitmap_to_base64 + giải mã). */
  private static RoaringBitmap loadTagFromSr(Connection c, int tag, Stats st) throws Exception {
    return st.time("C0 load one tag (SR bitmap_to_base64 + decode)", () -> {
      String b64;
      try (PreparedStatement ps = c.prepareStatement("SELECT bitmap_to_base64(bm) FROM bm_bench.tag_bitmap WHERE tag_id = ?")) {
        ps.setInt(1, tag);
        try (ResultSet rs = ps.executeQuery()) {
          rs.next();
          b64 = rs.getString(1);
        }
      }
      return BitmapCodec.decodeStarRocks(b64);
    });
  }

  /**
   * Test 6: từ lúc có yêu cầu đến khi service có toàn bộ user của segment. B = StarRocks tính và lưu
   * segment rồi lấy toàn bộ user về. C = nạp bitmap tag từ StarRocks vào cache của service (đo riêng
   * nạp lạnh) rồi tính segment trong service từ cache và duyệt hết user.
   */
  static void e2e(Connection c, MongoStore mg, Config cfg, Stats st) throws Exception {
    Map<Integer, RoaringBitmap> cache = new HashMap<>();
    if (cfg.runC()) {
      for (int rep = 0; rep < cfg.coldLoads(); rep++) {
        cache.clear();
        st.time("C1 cold load all tags (SR -> service cache)", () -> {
          for (int t = 1; t <= cfg.tags(); t++) {
            cache.put(t, loadTagFromSr(c, t, st));
          }
          return null;
        });
      }
      long heap = cache.values().stream().mapToLong(RoaringBitmap::getLongSizeInBytes).sum();
      System.out.printf("cache: %d tag, %.0fMB bitmap trong memory%n", cache.size(), heap / 1e6);
    }
    Random rng = new Random(cfg.seed());
    for (int s = 1; s <= cfg.segments(); s++) {
      final int seg = s;
      SegmentExpr expr = SegmentExpr.randomInRange(rng, cfg.tags(), cfg.leaves(), cfg::tagPctFraction, cfg.segMin(), cfg.segMax());
      long users = -1;
      if (cfg.runC()) {
        RoaringBitmap res = st.time("C2 compute and/or/not (cache)", () -> expr.evalPure(cache));
        long n = st.time("C3 get all users (iterate, in memory)", () -> {
          long k = 0;
          var it = res.getIntIterator();
          while (it.hasNext()) {
            it.next();
            k++;
          }
          return k;
        });
        st.add("C segment total: compute + all users (cache)", st.last("C2 compute and/or/not (cache)") + st.last("C3 get all users (iterate, in memory)"));
        st.note("segment_users_c", n);
        users = n;
      }
      if (cfg.runB()) {
        try (PreparedStatement del = c.prepareStatement("DELETE FROM bm_bench.segment_bitmap WHERE segment_id = ?")) {
          del.setInt(1, seg);
          del.execute();
        }
        String sql = expr.insertSql(seg);
        st.time("B total: SQL compute + store", () -> {
          try (var stmt = c.createStatement()) {
            return stmt.execute(sql);
          }
        });
        long n = st.time("B get all users: SQL unnest", () -> {
          try (var stmt = c.createStatement()) {
            stmt.setFetchSize(Integer.MIN_VALUE);
            long k = 0;
            try (ResultSet rs = stmt.executeQuery("SELECT u FROM bm_bench.segment_bitmap, unnest(bitmap_to_array(bm)) AS t(u)"
                + " WHERE segment_id = " + seg)) {
              while (rs.next()) {
                rs.getLong(1);
                k++;
              }
            }
            return k;
          }
        });
        st.add("B e2e total: compute + store + get all users (SR)", st.last("B total: SQL compute + store") + st.last("B get all users: SQL unnest"));
        st.note("segment_users_b", n);
        users = n;
      }
      System.out.printf("e2e %d/%d users=%d  %s%n", seg, cfg.segments(), users, expr);
    }
  }

  /**
   * Test 7, 8: nạp bitmap của một segment đã lưu (Mongo hoặc bảng bitmap của StarRocks) lên service, như khi
   * cache của service chưa có segment đó. Kết thúc khi service có RoaringBitmap trong bộ nhớ. Với --threads lớn hơn 1
   * nhiều segment được nạp cùng lúc (mỗi luồng một connection StarRocks; Mongo tối đa 10 chunk đồng thời).
   */
  static void loadSegments(Connection c0, MongoStore mg, Config cfg, Stats st) throws Exception {
    Random rng = new Random(cfg.seed() + 3);
    List<Integer> segs = new ArrayList<>();
    for (int i = 0; i < cfg.loads(); i++) {
      segs.add(1 + rng.nextInt(cfg.segments()));
    }
    java.util.concurrent.ExecutorService ex = java.util.concurrent.Executors.newFixedThreadPool(cfg.threads());
    ThreadLocal<Connection> conns = new ThreadLocal<>();
    List<Connection> opened = java.util.Collections.synchronizedList(new ArrayList<>());
    long wall = System.nanoTime();
    List<java.util.concurrent.Future<?>> fs = new ArrayList<>();
    for (int seg : segs) {
      fs.add(ex.submit(() -> {
        if (cfg.runA()) {
          long n = st.time("A load segment: mongo get chunks + deserialize", () -> {
            byte[] raw = mg.get(List.of(MongoStore.segmentKey(seg))).get(MongoStore.segmentKey(seg));
            return BitmapCodec.deserialize(raw).getLongCardinality();
          });
          st.note("users_loaded_a", n);
        }
        if (cfg.runB()) {
          Connection c = conns.get();
          if (c == null) {
            c = java.sql.DriverManager.getConnection(cfg.srUrl(), cfg.srUser(), cfg.srPassword());
            conns.set(c);
            opened.add(c);
          }
          final Connection cc = c;
          long n = st.time("B load segment: SR bitmap_to_base64 + decode", () -> {
            String b64;
            try (PreparedStatement ps = cc.prepareStatement("SELECT bitmap_to_base64(bm) FROM bm_bench.segment_bitmap WHERE segment_id = ?")) {
              ps.setInt(1, seg);
              try (ResultSet rs = ps.executeQuery()) {
                rs.next();
                b64 = rs.getString(1);
              }
            }
            return BitmapCodec.decodeStarRocks(b64).getLongCardinality();
          });
          st.note("users_loaded_b", n);
        }
        return null;
      }));
    }
    for (var f : fs) {
      f.get();
    }
    long wallMs = (System.nanoTime() - wall) / 1_000_000;
    ex.shutdown();
    for (Connection oc : opened) {
      oc.close();
    }
    st.note("wall_ms", wallMs);
    st.note("loads", cfg.loads());
    System.out.printf("load segment: %d lần, %d luồng, %d ms, %.1f lần/giây%n", cfg.loads(), cfg.threads(), wallMs, cfg.loads() * 1000.0 / wallMs);
  }

  /** Nạp bitmap của 1 segment từ bảng bitmap của SR (bitmap_to_base64 + giải mã). */
  private static RoaringBitmap loadSegmentFromSr(Connection c, int seg, Stats st, String stepName) throws Exception {
    return st.time(stepName, () -> {
      String b64;
      try (PreparedStatement ps = c.prepareStatement("SELECT bitmap_to_base64(bm) FROM bm_bench.segment_bitmap WHERE segment_id = ?")) {
        ps.setInt(1, seg);
        try (ResultSet rs = ps.executeQuery()) {
          rs.next();
          b64 = rs.getString(1);
        }
      }
      return BitmapCodec.decodeStarRocks(b64);
    });
  }

  /**
   * Test 9: check contains hoặc lấy một trang 1000 user của segment. B = chạy thẳng trên bitmap trong SR (một câu SQL mỗi lần);
   * C = trên bitmap đã nạp sẵn trong bộ nhớ của service (cache hit). Cùng danh sách thao tác cho cả hai để so kết quả.
   */
  static void ops(Connection c0, MongoStore mg, Config cfg, Stats st) throws Exception {
    Random rng = new Random(cfg.seed() + 4);
    List<Integer> ws = new ArrayList<>();
    for (int i = 1; i <= Math.min(cfg.workingSet(), cfg.segments()); i++) {
      ws.add(i);
    }
    Map<Integer, RoaringBitmap> cache = new java.util.concurrent.ConcurrentHashMap<>();
    if (cfg.runC()) {
      for (int seg : ws) {
        cache.put(seg, loadSegmentFromSr(c0, seg, st, "C0 load segment (SR bitmap_to_base64 + decode)"));
      }
      long mem = cache.values().stream().mapToLong(RoaringBitmap::getLongSizeInBytes).sum();
      System.out.printf("cache: %d segment, %.0fMB bitmap trong memory%n", cache.size(), mem / 1e6);
    }
    int[][] work = new int[cfg.ops()][2];
    for (int i = 0; i < cfg.ops(); i++) {
      work[i][0] = ws.get(rng.nextInt(ws.size()));
      work[i][1] = rng.nextInt(cfg.universe());
    }
    boolean contains = cfg.op().equals("contains");
    java.util.concurrent.ExecutorService ex = java.util.concurrent.Executors.newFixedThreadPool(cfg.threads());
    ThreadLocal<Connection> conns = new ThreadLocal<>();
    List<Connection> opened = java.util.Collections.synchronizedList(new ArrayList<>());
    long wall = System.nanoTime();
    List<java.util.concurrent.Future<?>> fs = new ArrayList<>();
    for (int[] w : work) {
      fs.add(ex.submit(() -> {
        int seg = w[0];
        int val = w[1];
        if (cfg.runC()) {
          RoaringBitmap bm = cache.get(seg);
          if (contains) {
            boolean r = st.time("C contains (cache hit)", () -> bm.contains(val));
            st.note("contains_true", r ? 1 : 0);
          } else {
            int n = st.time("C get 1000 users page (cache hit)", () -> {
              var it = bm.getBatchIterator();
              it.advanceIfNeeded(val);
              int[] buf = new int[1000];
              return it.nextBatch(buf);
            });
            st.note("page_users", n);
          }
        }
        if (cfg.runB()) {
          Connection c = conns.get();
          if (c == null) {
            c = java.sql.DriverManager.getConnection(cfg.srUrl(), cfg.srUser(), cfg.srPassword());
            conns.set(c);
            opened.add(c);
          }
          final Connection cc = c;
          if (contains) {
            boolean r = st.time("B contains: SR bitmap_contains", () -> {
              try (PreparedStatement ps = cc.prepareStatement("SELECT bitmap_contains(bm, ?) FROM bm_bench.segment_bitmap WHERE segment_id = ?")) {
                ps.setInt(1, val);
                ps.setInt(2, seg);
                try (ResultSet rs = ps.executeQuery()) {
                  return rs.next() && rs.getBoolean(1);
                }
              }
            });
            st.note("contains_true", r ? 1 : 0);
          } else {
            int n = st.time("B get 1000 users page: SR bitmap_subset_limit + unnest", () -> {
              try (PreparedStatement ps = cc.prepareStatement(
                  "SELECT u FROM bm_bench.segment_bitmap, unnest(bitmap_to_array(bitmap_subset_limit(bm, ?, 1000))) AS t(u) WHERE segment_id = ?")) {
                ps.setInt(1, val);
                ps.setInt(2, seg);
                int k = 0;
                try (ResultSet rs = ps.executeQuery()) {
                  while (rs.next()) {
                    rs.getLong(1);
                    k++;
                  }
                }
                return k;
              }
            });
            st.note("page_users", n);
          }
        }
        return null;
      }));
    }
    for (var f : fs) {
      f.get();
    }
    long wallMs = (System.nanoTime() - wall) / 1_000_000;
    ex.shutdown();
    for (Connection oc : opened) {
      oc.close();
    }
    st.note("wall_ms", wallMs);
    st.note("loads", cfg.ops());
    System.out.printf("ops %s: %d lần, %d luồng, %d ms, %.0f lần/giây%n", cfg.op(), cfg.ops(), cfg.threads(), wallMs, cfg.ops() * 1000.0 / wallMs);
  }
}
