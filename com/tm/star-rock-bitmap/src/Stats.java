package com.tm.starrockbitmap;

import com.sun.net.httpserver.HttpServer;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Gom thời gian đo theo tên metric và in bảng min/p50/p95/max. */
final class Stats {
  @FunctionalInterface
  interface Task<T> {
    T run() throws Exception;
  }

  private final Map<String, List<Long>> nanos = new LinkedHashMap<>();

  /** Chế độ export của pipeline A (agg|rows), gắn vào nhãn metric để Grafana tách hai lần chạy. */
  volatile String mode = "";

  private final Map<String, long[]> agg = new LinkedHashMap<>(); // {count, sumNs, lastNs}

  synchronized void add(String name, long ns) {
    nanos.computeIfAbsent(name, k -> new ArrayList<>()).add(ns);
    long[] a = agg.computeIfAbsent(name, k -> new long[3]);
    a[0]++;
    a[1] += ns;
    a[2] = ns;
  }

  private final Map<String, long[]> sizes = new LinkedHashMap<>(); // key kind|pipeline -> {count,sum,last,max}
  private final Map<String, Long> tagSizes = new LinkedHashMap<>(); // key pipeline|tag -> bytes

  /** Ghi kích thước bitmap (byte) của một tag hoặc segment; pipeline = A (blob Mongo) hoặc B (bitmap SR). */
  synchronized void size(String kind, String pipeline, int id, long bytes) {
    long[] a = sizes.computeIfAbsent(kind + "|" + pipeline, k -> new long[4]);
    a[0]++;
    a[1] += bytes;
    a[2] = bytes;
    a[3] = Math.max(a[3], bytes);
    if (kind.equals("tag")) tagSizes.put(pipeline + "|" + id, bytes);
  }

  private String variant(String pipeline) {
    return pipeline.equals("A") ? "mongo-" + mode : pipeline.equals("B") ? "sr" : "";
  }

  /** Giai đoạn của metric: tag (tính tag bitmap), segment (tính segment), read, hoặc load. */
  static String phase(String name) {
    if (name.startsWith("load")) return "load";
    if (name.matches("^(A[123]|B1|[AB] tag total).*")) return "tag";
    if (name.matches("^(A[4-7]|[AB] total).*")) return "segment";
    return "read";
  }

  /** Mở /metrics (Prometheus text) để Grafana vẽ latency theo từng bước. */
  void serve(int port) throws Exception {
    HttpServer srv = HttpServer.create(new InetSocketAddress(port), 0);
    srv.createContext("/metrics", ex -> {
      byte[] body = metricsText().getBytes(StandardCharsets.UTF_8);
      ex.getResponseHeaders().add("Content-Type", "text/plain; version=0.0.4");
      ex.sendResponseHeaders(200, body.length);
      ex.getResponseBody().write(body);
      ex.close();
    });
    srv.setExecutor(null);
    srv.start();
  }

  private synchronized String metricsText() {
    StringBuilder sb = new StringBuilder();
    for (var e : agg.entrySet()) {
      String n = e.getKey();
      String pl = n.startsWith("B") ? "B" : n.startsWith("A") ? "A" : "sr";
      String l = String.format("{step=\"%s\",phase=\"%s\",pipeline=\"%s\",mode=\"%s\",variant=\"%s\"}", n.replace("\"", ""),
          phase(n), pl, mode, variant(pl));
      long[] a = e.getValue();
      sb.append("bench_latency_ms_last").append(l).append(' ').append(a[2] / 1e6).append('\n');
      sb.append("bench_latency_ms_sum").append(l).append(' ').append(a[1] / 1e6).append('\n');
      sb.append("bench_latency_ms_count").append(l).append(' ').append(a[0]).append('\n');
    }
    for (var e : sizes.entrySet()) {
      String[] k = e.getKey().split("\\|");
      String l = String.format("{kind=\"%s\",pipeline=\"%s\",variant=\"%s\"}", k[0], k[1], variant(k[1]));
      long[] a = e.getValue();
      sb.append("bench_size_bytes_count").append(l).append(' ').append(a[0]).append('\n');
      sb.append("bench_size_bytes_sum").append(l).append(' ').append(a[1]).append('\n');
      sb.append("bench_size_bytes_last").append(l).append(' ').append(a[2]).append('\n');
      sb.append("bench_size_bytes_max").append(l).append(' ').append(a[3]).append('\n');
    }
    for (var e : tagSizes.entrySet()) {
      String[] k = e.getKey().split("\\|");
      sb.append(String.format("bench_tag_size_bytes{tag=\"%02d\",pipeline=\"%s\",variant=\"%s\"} %d%n",
          Integer.parseInt(k[1]), k[0], variant(k[0]), e.getValue()));
    }
    return sb.toString();
  }

  synchronized long last(String name) {
    List<Long> v = nanos.get(name);
    return v.get(v.size() - 1);
  }

  /** Chạy task, ghi thời gian theo name, trả kết quả của task. */
  <T> T time(String name, Task<T> task) throws Exception {
    long t = System.nanoTime();
    try {
      return task.run();
    } finally {
      add(name, System.nanoTime() - t);
    }
  }

  synchronized void print() {
    System.out.printf("%n%-34s %5s %10s %10s %10s %10s%n", "metric", "n", "min", "p50", "p95", "max");
    for (var e : nanos.entrySet()) {
      List<Long> v = new ArrayList<>(e.getValue());
      v.sort(Long::compare);
      int n = v.size();
      System.out.printf(
          "%-34s %5d %10s %10s %10s %10s%n",
          e.getKey(), n, fmt(v.get(0)), fmt(v.get((int) ((n - 1) * 0.5))),
          fmt(v.get((int) ((n - 1) * 0.95))), fmt(v.get(n - 1)));
    }
  }

  private static String fmt(long ns) {
    double ms = ns / 1e6;
    return ms >= 1000 ? String.format("%.2fs", ms / 1000) : String.format("%.2fms", ms);
  }
}
