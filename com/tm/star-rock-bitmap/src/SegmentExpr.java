package com.tm.starrockbitmap;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Random;
import java.util.stream.Collectors;
import org.roaringbitmap.RoaringBitmap;

/** Cây biểu thức của 1 segment; mỗi lá là 1 tag. */
final class SegmentExpr {
  static final char TAG = 'T';
  static final char AND = '&';
  static final char OR = '|';
  static final char AND_NOT = '-'; // l AND NOT r

  final char op;
  final int tag;
  final SegmentExpr l;
  final SegmentExpr r;

  private SegmentExpr(char op, int tag, SegmentExpr l, SegmentExpr r) {
    this.op = op;
    this.tag = tag;
    this.l = l;
    this.r = r;
  }

  /**
   * Biểu thức ngẫu nhiên có đúng {@code leaves} tag khác nhau, trộn AND (50%), OR (30%), AND NOT
   * (20%).
   */
  static SegmentExpr random(Random rng, int tags, int leaves) {
    List<Integer> ids = new ArrayList<>();
    for (int t = 1; t <= tags; t++) {
      ids.add(t);
    }
    java.util.Collections.shuffle(ids, rng);
    List<SegmentExpr> pool = new ArrayList<>();
    for (int t : ids.subList(0, leaves)) {
      pool.add(new SegmentExpr(TAG, t, null, null));
    }
    while (pool.size() > 1) {
      SegmentExpr a = pool.remove(rng.nextInt(pool.size()));
      int j = rng.nextInt(pool.size());
      int p = rng.nextInt(10);
      char op = p < 5 ? AND : p < 8 ? OR : AND_NOT;
      pool.set(j, new SegmentExpr(op, 0, a, pool.get(j)));
    }
    return pool.get(0);
  }

  List<Integer> tagIds() {
    List<Integer> out = new ArrayList<>();
    collect(out);
    return out;
  }

  private void collect(List<Integer> out) {
    if (op == TAG) {
      out.add(tag);
    } else {
      l.collect(out);
      r.collect(out);
    }
  }

  /** Tính trong memory. Mutate bitmap của lá, nên lá phải là bản riêng của lần eval này. */
  RoaringBitmap eval(Map<Integer, RoaringBitmap> leaf) {
    if (op == TAG) {
      return leaf.get(tag);
    }
    RoaringBitmap a = l.eval(leaf);
    RoaringBitmap b = r.eval(leaf);
    switch (op) {
      case AND -> a.and(b);
      case OR -> a.or(b);
      default -> a.andNot(b);
    }
    return a;
  }

  private String sql() {
    return switch (op) {
      case TAG -> "t" + tag + ".bm";
      case AND -> "bitmap_and(" + l.sql() + ", " + r.sql() + ")";
      case OR -> "bitmap_or(" + l.sql() + ", " + r.sql() + ")";
      default -> "bitmap_andnot(" + l.sql() + ", " + r.sql() + ")";
    };
  }

  /** INSERT segment vào SR: mỗi tag là 1 alias t<tag> join từ tag_bitmap. */
  String insertSql(int segmentId) {
    String from =
        tagIds().stream()
            .map(t -> "(SELECT bitmap_union(bm) AS bm FROM bm_bench.tag_bitmap WHERE tag_id = "
                + t + ") t" + t)
            .collect(Collectors.joining(" CROSS JOIN "));
    return "INSERT INTO bm_bench.segment_bitmap SELECT " + segmentId + ", " + sql() + " FROM " + from;
  }

  @Override
  public String toString() {
    return switch (op) {
      case TAG -> "t" + tag;
      case AND -> "(" + l + " AND " + r + ")";
      case OR -> "(" + l + " OR " + r + ")";
      default -> "(" + l + " AND NOT " + r + ")";
    };
  }
}
