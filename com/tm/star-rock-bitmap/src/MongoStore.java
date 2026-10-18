package com.tm.starrockbitmap;

import com.mongodb.client.MongoClient;
import com.mongodb.client.MongoClients;
import com.mongodb.client.MongoCollection;
import com.mongodb.client.model.Filters;
import com.mongodb.client.model.Indexes;
import com.mongodb.client.model.ReplaceOptions;
import java.io.ByteArrayOutputStream;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.Semaphore;
import org.bson.Document;
import org.bson.types.Binary;

/**
 * Lưu blob bitmap (roaring đã serialize) trong Mongo thành các chunk tối đa {@code --chunk-bytes}
 * byte (mặc định 8MB), mỗi chunk một document {_id: "<tên>#<số chunk>", n: tổng số chunk, data}. Tối
 * đa {@value #MAX_CONCURRENT} chunk đọc hoặc ghi đồng thời trên toàn bộ client, để không nổ
 * connection Mongo.
 */
final class MongoStore implements AutoCloseable {
  static final int MAX_CONCURRENT = 10;

  private final int chunkBytes;
  private final Semaphore ops = new Semaphore(MAX_CONCURRENT);
  private final ExecutorService pool = Executors.newFixedThreadPool(MAX_CONCURRENT);
  private final MongoClient client;
  private final MongoCollection<Document> chunks;

  MongoStore(String uri, String dbName, int chunkBytes) {
    this.chunkBytes = chunkBytes;
    client = MongoClients.create(uri);
    chunks = client.getDatabase(dbName).getCollection("bitmap_chunks");
    chunks.createIndex(Indexes.ascending("name"));
  }

  /** Cắt blob thành các phần tối đa max byte. */
  static List<byte[]> slice(byte[] blob, int max) {
    List<byte[]> out = new ArrayList<>();
    for (int off = 0; off < blob.length || out.isEmpty(); off += max) {
      out.add(java.util.Arrays.copyOfRange(blob, off, Math.min(blob.length, off + max)));
    }
    return out;
  }

  static byte[] join(List<byte[]> parts) {
    ByteArrayOutputStream out = new ByteArrayOutputStream();
    for (byte[] p : parts) {
      out.writeBytes(p);
    }
    return out.toByteArray();
  }

  /** Ghi (ghi đè) blob thành các chunk, tối đa 10 chunk đồng thời. Trả về số chunk. */
  int put(String name, byte[] blob) throws Exception {
    List<byte[]> parts = slice(blob, chunkBytes);
    List<Future<?>> fs = new ArrayList<>();
    for (int i = 0; i < parts.size(); i++) {
      final int idx = i;
      fs.add(pool.submit(() -> {
        ops.acquireUninterruptibly();
        try {
          Document d = new Document("_id", name + "#" + idx).append("name", name).append("chunk", idx)
              .append("n", parts.size()).append("data", new Binary(parts.get(idx)));
          chunks.replaceOne(Filters.eq("_id", d.get("_id")), d, new ReplaceOptions().upsert(true));
        } finally {
          ops.release();
        }
        return null;
      }));
    }
    for (Future<?> f : fs) {
      f.get();
    }
    return parts.size();
  }

  private Document readChunk(String name, int idx) {
    ops.acquireUninterruptibly();
    try {
      return chunks.find(Filters.eq("_id", name + "#" + idx)).first();
    } finally {
      ops.release();
    }
  }

  /** Đọc các blob (mỗi blob gồm 1 hay nhiều chunk), tối đa 10 chunk đồng thời. */
  Map<String, byte[]> get(List<String> names) throws Exception {
    Map<String, Future<Document>> first = new HashMap<>();
    for (String n : names) {
      first.put(n, pool.submit(() -> readChunk(n, 0)));
    }
    Map<String, List<Future<Document>>> rest = new HashMap<>();
    Map<String, Document> head = new HashMap<>();
    for (String n : names) {
      Document d = first.get(n).get();
      if (d == null) {
        throw new IllegalStateException("không có blob " + n + " trong Mongo");
      }
      head.put(n, d);
      List<Future<Document>> more = new ArrayList<>();
      for (int i = 1; i < d.getInteger("n"); i++) {
        final int idx = i;
        more.add(pool.submit(() -> readChunk(n, idx)));
      }
      rest.put(n, more);
    }
    Map<String, byte[]> out = new HashMap<>();
    for (String n : names) {
      List<byte[]> parts = new ArrayList<>();
      parts.add(((Binary) head.get(n).get("data")).getData());
      for (Future<Document> f : rest.get(n)) {
        parts.add(((Binary) f.get().get("data")).getData());
      }
      out.put(n, join(parts));
    }
    return out;
  }

  static String tagKey(int tag) {
    return "tag-" + tag;
  }

  static String segmentKey(int segment) {
    return "segment-" + segment;
  }

  @Override
  public void close() {
    pool.shutdown();
    client.close();
  }
}
