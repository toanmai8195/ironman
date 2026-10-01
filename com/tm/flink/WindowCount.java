package com.tm.flink;

import java.time.Instant;
import org.apache.flink.streaming.api.functions.windowing.ProcessWindowFunction;
import org.apache.flink.streaming.api.windowing.windows.TimeWindow;
import org.apache.flink.util.Collector;

/** Đếm số event trong một window event-time theo key "bảng|op", in ra một dòng mô tả. */
public class WindowCount extends ProcessWindowFunction<CdcRecord, String, String, TimeWindow> {
    @Override
    public void process(String key, Context ctx, Iterable<CdcRecord> events, Collector<String> out) {
        long count = 0;
        for (CdcRecord ignored : events) {
            count++;
        }
        out.collect(format(key, ctx.window().getStart(), ctx.window().getEnd(), count));
    }

    static String format(String key, long startMs, long endMs, long count) {
        return String.format("WINDOW [%s, %s) %s count=%d", Instant.ofEpochMilli(startMs), Instant.ofEpochMilli(endMs), key, count);
    }

    /** Key để nhóm: bảng nguồn + loại thao tác. */
    static String key(CdcRecord r) {
        return r.sourceTable + "|" + CdcEvent.opName(r.op);
    }
}
