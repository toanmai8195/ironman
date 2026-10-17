package com.tm.starrockbitmap;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.Base64;
import org.roaringbitmap.RoaringBitmap;

/** Serialize/deserialize roaring (portable format) và giải mã bitmap native của StarRocks. */
final class BitmapCodec {
  private BitmapCodec() {}

  static byte[] serialize(RoaringBitmap bm) throws IOException {
    bm.runOptimize();
    ByteArrayOutputStream bos = new ByteArrayOutputStream(bm.serializedSizeInBytes());
    try (DataOutputStream out = new DataOutputStream(bos)) {
      bm.serialize(out);
    }
    return bos.toByteArray();
  }

  static RoaringBitmap deserialize(byte[] b, int off, int len) throws IOException {
    RoaringBitmap bm = new RoaringBitmap();
    bm.deserialize(new DataInputStream(new ByteArrayInputStream(b, off, len)));
    return bm;
  }

  static RoaringBitmap deserialize(byte[] b) throws IOException {
    return deserialize(b, 0, b.length);
  }

  /**
   * Giải mã output của {@code bitmap_to_base64} (định dạng BitmapValue của StarRocks): byte đầu là
   * type, phần sau phụ thuộc type. Theo {@code StarrocksBitmapCodec} của core-service (đã kiểm
   * chứng trên SR 3.5.19):
   *
   * <pre>
   *   0 EMPTY, 1 SINGLE32 (uint32 LE), 2 BITMAP32 (portable roaring),
   *   3 SINGLE64 (uint64 LE), 4 BITMAP64 (không hỗ trợ),
   *   10 SET: uint32 LE count rồi count giá trị uint64 LE
   * </pre>
   *
   * Giá trị 64-bit phải nằm trong 32-bit, nếu không báo lỗi thay vì cắt bớt.
   */
  static RoaringBitmap decodeStarRocks(String base64) throws IOException {
    byte[] b = Base64.getDecoder().decode(base64);
    if (b.length == 0 || b[0] == 0) {
      return new RoaringBitmap(); // EMPTY
    }
    ByteBuffer buf = ByteBuffer.wrap(b).order(ByteOrder.LITTLE_ENDIAN);
    switch (b[0]) {
      case 1: // SINGLE32
        return RoaringBitmap.bitmapOf(buf.getInt(1));
      case 2: // BITMAP32
        return deserialize(b, 1, b.length - 1);
      case 3: // SINGLE64
        return RoaringBitmap.bitmapOf(narrow(buf.getLong(1)));
      case 10: // SET
        {
          long n = Integer.toUnsignedLong(buf.getInt(1));
          if (b.length - 5 != n * Long.BYTES) {
            throw new IOException("SR bitmap SET bị cắt cụt: count=" + n + ", bytes=" + (b.length - 5));
          }
          RoaringBitmap bm = new RoaringBitmap();
          for (int i = 0; i < n; i++) {
            bm.add(narrow(buf.getLong(5 + 8 * i)));
          }
          return bm;
        }
      default:
        throw new IOException("SR bitmap type " + b[0] + " chưa hỗ trợ (BITMAP64 hoặc type lạ)");
    }
  }

  private static int narrow(long v) throws IOException {
    if (v < 0 || v > 0xFFFF_FFFFL) {
      throw new IOException("giá trị " + v + " không vừa 32-bit");
    }
    return (int) v;
  }
}
