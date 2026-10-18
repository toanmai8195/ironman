package com.tm.flink;

/**
 * Một event CDC đã làm phẳng thành các cột cố định (dạng sẽ ghi vào bronze).
 * POJO (public field + constructor rỗng) để Flink dùng POJO serializer thay vì Kryo.
 */
public class CdcRecord {
    public String sourceTable;
    public String op;
    public boolean deleted;
    public long tsMs;
    public long lsn;
    public String topic;
    public int partition;
    public long offset;
    /** Trạng thái dòng sau thay đổi: after, hoặc before nếu là delete. */
    public String row;
    public String before;
    public String after;

    public CdcRecord() {}

    public static CdcRecord of(CdcEvent e, String topic, int partition, long offset) {
        CdcRecord r = new CdcRecord();
        r.sourceTable = e.table;
        r.op = e.op;
        r.deleted = "d".equals(e.op);
        r.tsMs = e.tsMs;
        r.lsn = e.lsn;
        r.topic = topic;
        r.partition = partition;
        r.offset = offset;
        r.before = e.before;
        r.after = e.after;
        r.row = r.deleted ? e.before : e.after;
        return r;
    }
}
