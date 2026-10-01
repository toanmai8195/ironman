package com.tm.flink;

import static org.junit.Assert.assertEquals;

import org.junit.Test;

public class WindowCountTest {
    @Test
    public void formatAndKey() {
        assertEquals("WINDOW [1970-01-01T00:01:00Z, 1970-01-01T00:02:00Z) public.orders|update count=3",
                WindowCount.format("public.orders|update", 60_000, 120_000, 3));

        CdcRecord r = CdcRecord.of(CdcEvent.fromJson("{\"before\":null,\"after\":{\"id\":1},"
                + "\"source\":{\"schema\":\"public\",\"table\":\"orders\",\"lsn\":1},\"op\":\"d\",\"ts_ms\":1}"), "t", 0, 0);
        assertEquals("public.orders|delete", WindowCount.key(r));
    }
}
