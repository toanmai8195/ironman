package com.tm.flink;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertThrows;

import org.junit.Test;

public class CdcEventTest {
    @Test
    public void update() {
        CdcEvent e = CdcEvent.fromJson("{\"before\":{\"id\":1,\"status\":\"NEW\"},\"after\":{\"id\":1,\"status\":\"PAID\"},"
                + "\"source\":{\"schema\":\"public\",\"table\":\"orders\",\"lsn\":99},\"op\":\"u\",\"ts_ms\":42}");
        assertEquals("public.orders", e.table);
        assertEquals("u", e.op);
        assertEquals(42, e.tsMs);
        assertEquals(99, e.lsn);
        assertEquals("{\"id\":1,\"status\":\"NEW\"}", e.before);
        assertEquals("[update] public.orders before={\"id\":1,\"status\":\"NEW\"} after={\"id\":1,\"status\":\"PAID\"}", e.toString());
    }

    @Test
    public void snapshotHasNoBefore() {
        CdcEvent e = CdcEvent.fromJson("{\"before\":null,\"after\":{\"id\":1},"
                + "\"source\":{\"schema\":\"public\",\"table\":\"customers\"},\"op\":\"r\",\"ts_ms\":1}");
        assertNull(e.before);
        assertEquals("snapshot", CdcEvent.opName(e.op));
    }

    @Test
    public void rejectsBadInput() {
        assertThrows(IllegalArgumentException.class, () -> CdcEvent.fromJson("{"));
        assertThrows(IllegalArgumentException.class, () -> CdcEvent.fromJson("{\"a\":1}"));
    }
}
