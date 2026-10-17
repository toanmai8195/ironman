package com.tm.starrockbitmap;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Random;
import org.junit.Test;
import org.roaringbitmap.RoaringBitmap;

public class SegmentExprTest {
  @Test
  public void randomExprHasDistinctLeavesAndMatchesBitSetEval() throws Exception {
    Random rng = new Random(7);
    for (int round = 0; round < 50; round++) {
      SegmentExpr e = SegmentExpr.random(rng, 15, 10);
      List<Integer> ids = e.tagIds();
      assertEquals(10, ids.stream().distinct().count());

      Map<Integer, RoaringBitmap> leaf = new HashMap<>();
      Map<Integer, java.util.BitSet> ref = new HashMap<>();
      for (int t : ids) {
        RoaringBitmap bm = new RoaringBitmap();
        java.util.BitSet bs = new java.util.BitSet();
        for (int u = 0; u < 5000; u++) {
          if (rng.nextInt(3) == 0) {
            bm.add(u);
            bs.set(u);
          }
        }
        leaf.put(t, BitmapCodec.deserialize(BitmapCodec.serialize(bm))); // qua codec như thật
        ref.put(t, bs);
      }
      RoaringBitmap got = e.eval(leaf);
      java.util.BitSet want = evalRef(e, ref);
      assertEquals(want.cardinality(), got.getCardinality());
      for (int u = 0; u < 5000; u++) {
        assertEquals(want.get(u), got.contains(u));
      }
    }
  }

  private static java.util.BitSet evalRef(SegmentExpr e, Map<Integer, java.util.BitSet> ref) {
    if (e.op == SegmentExpr.TAG) {
      return (java.util.BitSet) ref.get(e.tag).clone();
    }
    java.util.BitSet a = evalRef(e.l, ref);
    java.util.BitSet b = evalRef(e.r, ref);
    switch (e.op) {
      case SegmentExpr.AND -> a.and(b);
      case SegmentExpr.OR -> a.or(b);
      default -> a.andNot(b);
    }
    return a;
  }

  @Test
  public void insertSqlReferencesEveryTagOnce() {
    SegmentExpr e = SegmentExpr.random(new Random(1), 12, 10);
    String sql = e.insertSql(3);
    assertTrue(sql.startsWith("INSERT INTO bm_bench.segment_bitmap SELECT 3, "));
    for (int t : e.tagIds()) {
      assertEquals(1, sql.split("\\) t" + t + "(?!\\d)", -1).length - 1);
    }
  }

  @Test
  public void decodesStarRocksSingleAndSet() throws Exception {
    // type 1 (SINGLE32) value 7; type 10 (SET) {1,2} với giá trị 8 byte
    String single = java.util.Base64.getEncoder().encodeToString(new byte[] {1, 7, 0, 0, 0});
    assertEquals(RoaringBitmap.bitmapOf(7), BitmapCodec.decodeStarRocks(single));
    String set = java.util.Base64.getEncoder().encodeToString(new byte[] {10, 2, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 2, 0, 0, 0, 0, 0, 0, 0});
    assertEquals(RoaringBitmap.bitmapOf(1, 2), BitmapCodec.decodeStarRocks(set));
  }

  @Test
  public void blobSliceAndJoinRoundTrip() {
    byte[] blob = new byte[20_000_001];
    new Random(5).nextBytes(blob);
    java.util.List<byte[]> parts = MongoStore.slice(blob, 8_000_000);
    assertEquals(3, parts.size());
    for (byte[] p : parts) {
      assertTrue(p.length <= 8_000_000);
    }
    assertTrue(java.util.Arrays.equals(blob, MongoStore.join(parts)));
    assertEquals(1, MongoStore.slice(new byte[6_300_000], 8_000_000).size());
    assertEquals(1, MongoStore.slice(new byte[0], 8_000_000).size());
  }
}
