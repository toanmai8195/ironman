package com.tm.starrockbitmap;

import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Random;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import org.roaringbitmap.RoaringBitmap;

/** Các bước đo: etl (SR -> bitmap), segment (compute + lưu), read (contains / get users). */
final class Bench {
  private Bench() {}

  /** Đo bước "bảng SR -> bitmap" cho cả 2 pipeline. */
  static void etl(Connection c, MongoStore mg, Config cfg, Stats st) throws Exception {
    long sizeTotal = 0;
    for (int t = 1; t <= cfg.tags(); t++) {
      final int tag = t;
      long card = -1;
      int blobLen = 0;
      if (cfg.runA()) {
        // A: gold -> service -> bitmap -> Mongo
        RoaringBitmap bm = st.time("A1 total: SR -> bitmap", () -> Sr.fetchTag(c, cfg, cfg.attributeOf(tag), tag, st));
        byte[] blob = st.time("A2 serialize", () -> BitmapCodec.serialize(bm));
        sizeTotal += blob.length;
        st.time("A3 mongo put", () -> { mg.put(MongoStore.tagKey(tag), blob); return null; });
        card = bm.getLongCardinality();
        blobLen = blob.length;
        st.add("A tag total: gold -> mongo",
            st.last("A1 total: SR -> bitmap") + st.last("A2 serialize") + st.last("A3 mongo put"));
        st.size("tag", "A", tag, blob.length);
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
      }
      if (cfg.runB()) {
        st.add("B tag total: gold -> sr", st.last("B1 SR gold -> tag_bitmap"));
        st.size("tag", "B", tag, Sr.bitmapBytes(c, "SELECT bm FROM bm_bench.tag_bitmap WHERE tag_id = " + tag));
      }
      System.out.printf("etl tag %d/%d card=%d blob=%.1fMB%n", t, cfg.tags(), card, blobLen / 1e6);
    }
    System.out.printf("avg mongo blob/tag: %.1fMB%n", sizeTotal / (double) cfg.tags() / 1e6);
  }

  /** Đo compute + lưu segment cho cả 2 pipeline, đối chiếu cardinality. */
  static void segment(Connection c, MongoStore mg, Config cfg, Stats st) throws Exception {
    Random rng = new Random(cfg.seed());
    ExecutorService pool = Executors.newFixedThreadPool(cfg.leaves());
    try {
      for (int s = 1; s <= cfg.segments(); s++) {
        final int seg = s;
        SegmentExpr expr = SegmentExpr.randomInRange(rng, cfg.tags(), cfg.leaves(), cfg::tagPctFraction, cfg.segMin(), cfg.segMax());

        RoaringBitmap res = null;
        byte[] blob = new byte[0];
        if (cfg.runA()) {
        // ---- A: Mongo -> service -> compute -> Mongo
        Map<Integer, RoaringBitmap> leaf = st.time("A4 fetch tags (parallel)", () -> {
          Map<Integer, RoaringBitmap> out = new ConcurrentHashMap<>();
          List<Future<?>> fs = new java.util.ArrayList<>();
          for (int t : expr.tagIds()) {
            fs.add(pool.submit(() -> {
              out.put(t, BitmapCodec.deserialize(mg.get(MongoStore.tagKey(t))));
              return null;
            }));
          }
          for (Future<?> f : fs) {
            f.get();
          }
          return out;
        });
        RoaringBitmap bmRes = st.time("A5 compute and/or/not", () -> expr.eval(leaf));
        res = bmRes;
        blob = st.time("A6 serialize", () -> BitmapCodec.serialize(bmRes));
        final byte[] blobF = blob;
        st.time("A7 mongo put segment", () -> { mg.put(MongoStore.segmentKey(seg), blobF); return null; });
        st.add("A total (fetch+compute+store)",
            st.last("A4 fetch tags (parallel)") + st.last("A5 compute and/or/not")
                + st.last("A6 serialize") + st.last("A7 mongo put segment"));
        }

        long cardB = -1;
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

        // ---- đối chiếu
        try (PreparedStatement ps = c.prepareStatement(
            "SELECT bitmap_count(bm) FROM bm_bench.segment_bitmap WHERE segment_id = ?")) {
          ps.setInt(1, seg);
          try (ResultSet rs = ps.executeQuery()) {
            rs.next();
            cardB = rs.getLong(1);
          }
        }
        }
        if (cfg.runB()) st.size("segment", "B", seg, Sr.bitmapBytes(c, "SELECT bm FROM bm_bench.segment_bitmap WHERE segment_id = " + seg));
        if (cfg.runA()) st.size("segment", "A", seg, blob.length);
        long cardA = res == null ? -1 : res.getLongCardinality();
        String check = cardA < 0 || cardB < 0 ? "-" : cardA == cardB ? "OK" : "MISMATCH";
        System.out.printf("segment %d card A=%d B=%d %s blob=%.1fMB  %s%n", seg, cardA, cardB, check, blob.length / 1e6, expr);
      }
    } finally {
      pool.shutdown();
    }
  }

  /** Đo 2 nhu cầu đọc segment: check contains và lấy 1 trang user. */
  static void read(Connection c, MongoStore mg, Config cfg, Stats st) throws Exception {
    Random rng = new Random(cfg.seed() + 1);
    for (int i = 0; i < cfg.reads(); i++) {
      int seg = 1 + rng.nextInt(cfg.segments());
      int user = 1 + rng.nextInt(cfg.universe());

      if (cfg.runA()) {
      st.time("A contains: mongo get + check", () ->
          BitmapCodec.deserialize(mg.get(MongoStore.segmentKey(seg))).contains(user));
      }
      if (cfg.runB()) st.time("B contains: SQL bitmap_contains", () -> {
        try (PreparedStatement ps = c.prepareStatement(
            "SELECT bitmap_contains(bm, ?) FROM bm_bench.segment_bitmap WHERE segment_id = ?")) {
          ps.setInt(1, user);
          ps.setInt(2, seg);
          try (ResultSet rs = ps.executeQuery()) {
            return rs.next() && rs.getBoolean(1);
          }
        }
      });

      if (cfg.runA()) st.time("A get 1000 users: get + iterate", () -> {
        RoaringBitmap bm = BitmapCodec.deserialize(mg.get(MongoStore.segmentKey(seg)));
        int[] page = new int[1000];
        bm.getIntIterator().hasNext();
        var it = bm.getBatchIterator();
        return it.nextBatch(page);
      });
      if (cfg.runB()) st.time("B get 1000 users: SQL unnest", () -> {
        try (PreparedStatement ps = c.prepareStatement(
            "SELECT u FROM bm_bench.segment_bitmap, unnest(bitmap_to_array(bm)) AS t(u)"
                + " WHERE segment_id = ? LIMIT 1000")) {
          ps.setInt(1, seg);
          int n = 0;
          try (ResultSet rs = ps.executeQuery()) {
            while (rs.next()) {
              rs.getLong(1);
              n++;
            }
          }
          return n;
        }
      });
    }
  }

  /** Đo lấy toàn bộ user của segment: A = get blob Mongo + duyệt hết, B = SQL unnest toàn bộ. */
  static void getAll(Connection c, MongoStore mg, Config cfg, Stats st) throws Exception {
    Random rng = new Random(cfg.seed() + 2);
    for (int i = 0; i < cfg.fullGets(); i++) {
      int seg = 1 + rng.nextInt(cfg.segments());
      long a = -1;
      long b = -1;
      if (cfg.runA()) {
        a = st.time("A get all users: mongo get + iterate", () -> {
          RoaringBitmap bm = BitmapCodec.deserialize(mg.get(MongoStore.segmentKey(seg)));
          long n = 0;
          var it = bm.getIntIterator();
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
}
