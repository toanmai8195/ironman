package com.tm.starrockbitmap;

import java.util.HashMap;
import java.util.Map;

/** Cấu hình benchmark, đọc từ flag dạng {@code --key=value} hoặc {@code --key value}. */
record Config(
    String srUrl,
    String srUser,
    String srPassword,
    String mongoUri,
    String mongoDb,
    int tags,
    int tagsPerAttribute,
    int removedPct,
    String goldCatalog,
    int universe,
    int minPct,
    int maxPct,
    int segments,
    int leaves,
    long seed,
    String export,
    String pipeline,
    int reads,
    double segMin,
    double segMax,
    int fullGets,
    String out) {

  /** Chạy pipeline A (Mongo + service). */
  boolean runA() {
    return pipeline.contains("a");
  }

  /** Chạy pipeline B (SR native). */
  boolean runB() {
    return pipeline.contains("b");
  }

  static final String GOLD_NAME = "aggregating_tag_not_mutex_most_recent";

  /** Gold nằm trong Iceberg (external catalog) khi có --gold-catalog, ngược lại là bảng native của SR. */
  boolean goldInIceberg() {
    return !goldCatalog.isEmpty();
  }

  /** Tên đầy đủ của bảng gold. */
  String goldTable() {
    return (goldInIceberg() ? goldCatalog + "." : "") + "bm_bench." + GOLD_NAME;
  }

  /** Phần trăm universe là thành viên của tag (rải min..max, xác định theo t). */
  int tagPct(int tag) {
    return minPct + (tag * 7) % (maxPct - minPct + 1);
  }

  double tagPctFraction(int tag) {
    return tagPct(tag) / 100.0;
  }

  /** Attribute chứa tag (tag 1..N chia đều cho attribute 1..). */
  int attributeOf(int tag) {
    return (tag - 1) / tagsPerAttribute + 1;
  }

  static Config parse(String[] args, int from) {
    Map<String, String> m = new HashMap<>();
    for (int i = from; i < args.length; i++) {
      String a = args[i];
      if (!a.startsWith("--")) {
        throw new IllegalArgumentException("flag không hợp lệ: " + a);
      }
      int eq = a.indexOf('=');
      if (eq > 0) {
        m.put(a.substring(2, eq), a.substring(eq + 1));
      } else {
        m.put(a.substring(2), args[++i]);
      }
    }
    return new Config(
        m.getOrDefault("sr", "jdbc:mysql://127.0.0.1:9030/?sessionVariables=query_timeout=7200"),
        m.getOrDefault("sr-user", "root"),
        m.getOrDefault("sr-password", ""),
        m.getOrDefault("mongo", "mongodb://127.0.0.1:27017"),
        m.getOrDefault("mongo-db", "bm_bench"),
        Integer.parseInt(m.getOrDefault("tags", "30")),
        Integer.parseInt(m.getOrDefault("tags-per-attribute", "5")),
        Integer.parseInt(m.getOrDefault("removed-pct", "5")),
        m.getOrDefault("gold-catalog", ""),
        Integer.parseInt(m.getOrDefault("universe", "50000000")),
        Integer.parseInt(m.getOrDefault("min-pct", "10")),
        Integer.parseInt(m.getOrDefault("max-pct", "20")),
        Integer.parseInt(m.getOrDefault("segments", "20")),
        Integer.parseInt(m.getOrDefault("leaves", "10")),
        Long.parseLong(m.getOrDefault("seed", "42")),
        m.getOrDefault("export", "agg"),
        m.getOrDefault("pipeline", "ab"),
        Integer.parseInt(m.getOrDefault("reads", "50")),
        Double.parseDouble(m.getOrDefault("seg-min", "0.105")),
        Double.parseDouble(m.getOrDefault("seg-max", "0.195")),
        Integer.parseInt(m.getOrDefault("full-gets", "40")),
        m.getOrDefault("out", ""));
  }
}
