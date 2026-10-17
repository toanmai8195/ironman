package com.tm.starrockbitmap;

import java.sql.Connection;
import java.sql.DriverManager;
import java.time.Duration;

/**
 * Benchmark segment bằng roaring bitmap: A) blob trong MongoDB + compute ở service, B) bitmap
 * native của StarRocks + compute bằng SQL.
 *
 * <p>Dùng: {@code Main <load|etl|segment|read|all> [--flag value ...]}
 */
public final class Main {
  private Main() {}

  public static void main(String[] args) throws Exception {
    if (args.length < 1) {
      System.err.println("usage: star-rock-bitmap <load|etl|segment|read|all> [--flag value ...]");
      System.exit(2);
    }
    String cmd = args[0];
    Config cfg = Config.parse(args, 1);
    Stats st = new Stats();
    st.mode = cfg.runA() ? cfg.export() : "sr";
    st.serve(Integer.parseInt(System.getenv().getOrDefault("BENCH_METRICS_PORT", "9464")));
    long start = System.nanoTime();
    try (Connection c = DriverManager.getConnection(cfg.srUrl(), cfg.srUser(), cfg.srPassword());
        MongoStore mg = new MongoStore(cfg.mongoUri(), cfg.mongoDb())) {
      switch (cmd) {
        case "load" -> Sr.load(c, cfg, st);
        case "etl" -> Bench.etl(c, mg, cfg, st);
        case "segment" -> Bench.segment(c, mg, cfg, st);
        case "read" -> Bench.read(c, mg, cfg, st);
        case "run" -> { // như all nhưng không load lại gold
          Bench.etl(c, mg, cfg, st);
          Bench.segment(c, mg, cfg, st);
          Bench.read(c, mg, cfg, st);
        }
        case "all" -> {
          Sr.load(c, cfg, st);
          Bench.etl(c, mg, cfg, st);
          Bench.segment(c, mg, cfg, st);
          Bench.read(c, mg, cfg, st);
        }
        default -> throw new IllegalArgumentException("lệnh không hợp lệ: " + cmd);
      }
    }
    st.print();
    System.out.println("\ntổng thời gian chạy: " + Duration.ofNanos(System.nanoTime() - start).toSeconds() + "s");
    System.exit(0); // đóng exporter /metrics
  }
}
