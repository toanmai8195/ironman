package com.tm.flink;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

/**
 * Một event CDC của Debezium (JSON, schemas.enable=false), rút gọn các field cần dùng.
 * before/after giữ nguyên dạng JSON string (null nếu không có), chưa tách theo cột.
 */
public final class CdcEvent {
    private static final ObjectMapper MAPPER = new ObjectMapper();

    public final String op;
    public final String table;
    public final long tsMs;
    public final long lsn;
    public final String before;
    public final String after;

    public CdcEvent(String op, String table, long tsMs, long lsn, String before, String after) {
        this.op = op;
        this.table = table;
        this.tsMs = tsMs;
        this.lsn = lsn;
        this.before = before;
        this.after = after;
    }

    /** op: c=create, u=update, d=delete, r=snapshot. */
    public static String opName(String op) {
        switch (op) {
            case "c": return "create";
            case "u": return "update";
            case "d": return "delete";
            case "r": return "snapshot";
            default: return op;
        }
    }

    /** Ném IllegalArgumentException nếu không phải envelope Debezium hợp lệ. */
    public static CdcEvent fromJson(String json) {
        try {
            JsonNode n = MAPPER.readTree(json);
            if (n == null || !n.hasNonNull("op") || !n.hasNonNull("source")) {
                throw new IllegalArgumentException("không phải envelope Debezium (thiếu op/source)");
            }
            JsonNode src = n.get("source");
            return new CdcEvent(
                    n.get("op").asText(),
                    src.path("schema").asText() + "." + src.path("table").asText(),
                    n.path("ts_ms").asLong(),
                    src.path("lsn").asLong(),
                    n.hasNonNull("before") ? n.get("before").toString() : null,
                    n.hasNonNull("after") ? n.get("after").toString() : null);
        } catch (java.io.IOException e) {
            throw new IllegalArgumentException("JSON không hợp lệ: " + e.getMessage(), e);
        }
    }

    @Override
    public String toString() {
        return "[" + opName(op) + "] " + table + " before=" + before + " after=" + after;
    }
}
