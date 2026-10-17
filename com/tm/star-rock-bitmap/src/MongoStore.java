package com.tm.starrockbitmap;

import com.mongodb.client.MongoClient;
import com.mongodb.client.MongoClients;
import com.mongodb.client.MongoDatabase;
import com.mongodb.client.gridfs.GridFSBucket;
import com.mongodb.client.gridfs.GridFSBuckets;
import com.mongodb.client.gridfs.model.GridFSFile;
import com.mongodb.client.gridfs.model.GridFSUploadOptions;
import com.mongodb.client.model.Filters;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;

/**
 * Lưu bitmap dạng blob trong GridFS, chia thành chunk {@value #CHUNK_SIZE} byte (8MB). Dùng GridFS
 * thay vì field binary vì bitmap 20M user có thể vượt giới hạn 16MB/document.
 */
final class MongoStore implements AutoCloseable {
  static final int CHUNK_SIZE = 8 * 1024 * 1024;
  private static final GridFSUploadOptions UPLOAD = new GridFSUploadOptions().chunkSizeBytes(CHUNK_SIZE);

  /** Tối đa số lần get (mỗi blob nhỏ hơn 1 chunk nên là 1 chunk) chạy đồng thời, để không nổ connection Mongo. */
  static final int MAX_CONCURRENT_GETS = 10;

  private final java.util.concurrent.Semaphore gets = new java.util.concurrent.Semaphore(MAX_CONCURRENT_GETS);
  private final MongoClient client;
  private final GridFSBucket bucket;

  MongoStore(String uri, String dbName) {
    client = MongoClients.create(uri);
    MongoDatabase db = client.getDatabase(dbName);
    bucket = GridFSBuckets.create(db);
  }

  /** Ghi đè blob theo name. */
  void put(String name, byte[] blob) {
    for (GridFSFile f : bucket.find(Filters.eq("filename", name))) {
      bucket.delete(f.getObjectId());
    }
    bucket.uploadFromStream(name, new ByteArrayInputStream(blob), UPLOAD);
  }

  byte[] get(String name) {
    gets.acquireUninterruptibly();
    try {
      ByteArrayOutputStream out = new ByteArrayOutputStream();
      bucket.downloadToStream(name, out);
      return out.toByteArray();
    } finally {
      gets.release();
    }
  }

  static String tagKey(int tag) {
    return "tag-" + tag;
  }

  static String segmentKey(int segment) {
    return "segment-" + segment;
  }

  @Override
  public void close() {
    client.close();
  }
}
