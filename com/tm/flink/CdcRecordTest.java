package com.tm.flink;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import org.apache.flink.util.Collector;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.junit.Test;

public class CdcRecordTest {
    private static final String UPDATE = "{\"before\":{\"id\":1,\"status\":\"NEW\"},\"after\":{\"id\":1,\"status\":\"PAID\"},"
            + "\"source\":{\"schema\":\"public\",\"table\":\"orders\",\"lsn\":7},\"op\":\"u\",\"ts_ms\":5}";
    private static final String DELETE = "{\"before\":{\"id\":2},\"after\":null,"
            + "\"source\":{\"schema\":\"public\",\"table\":\"orders\",\"lsn\":8},\"op\":\"d\",\"ts_ms\":6}";

    @Test
    public void rowIsAfterExceptDelete() {
        CdcRecord u = CdcRecord.of(CdcEvent.fromJson(UPDATE), "t", 1, 10);
        assertFalse(u.deleted);
        assertEquals("{\"id\":1,\"status\":\"PAID\"}", u.row);

        CdcRecord d = CdcRecord.of(CdcEvent.fromJson(DELETE), "t", 1, 11);
        assertTrue(d.deleted);
        assertEquals("{\"id\":2}", d.row);
        assertEquals(8, d.lsn);
    }

    @Test
    public void deserializerKeepsKafkaMetadataAndSkipsBadMessages() {
        CdcRecordDeserializer de = new CdcRecordDeserializer();
        List<CdcRecord> out = new ArrayList<>();
        Collector<CdcRecord> c = new Collector<CdcRecord>() {
            public void collect(CdcRecord r) { out.add(r); }
            public void close() {}
        };

        de.deserialize(rec(UPDATE.getBytes(StandardCharsets.UTF_8), 3), c);
        de.deserialize(rec(null, 4), c);                                            // tombstone
        de.deserialize(rec("{".getBytes(StandardCharsets.UTF_8), 5), c);            // JSON hỏng

        assertEquals(1, out.size());
        assertEquals("topic-x", out.get(0).topic);
        assertEquals(2, out.get(0).partition);
        assertEquals(3, out.get(0).offset);
    }

    private static ConsumerRecord<byte[], byte[]> rec(byte[] value, long offset) {
        return new ConsumerRecord<>("topic-x", 2, offset, null, value);
    }
}
