package com.tm.flink;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.apache.flink.table.data.RowData;
import org.junit.Test;

public class IcebergBronzeTest {
    @Test
    public void toRowMatchesSchemaOrder() {
        CdcRecord r = CdcRecord.of(CdcEvent.fromJson("{\"before\":null,\"after\":{\"id\":3},"
                + "\"source\":{\"schema\":\"public\",\"table\":\"customers\",\"lsn\":9},\"op\":\"c\",\"ts_ms\":5}"),
                "ironman.public.customers", 2, 17);

        RowData row = IcebergBronze.toRow(r, 1000);

        assertEquals(IcebergBronze.SCHEMA.columns().size(), row.getArity());
        assertEquals("public.customers", row.getString(0).toString());
        assertEquals("c", row.getString(1).toString());
        assertFalse(row.getBoolean(2));
        assertEquals(9, row.getLong(4));
        assertEquals(2, row.getInt(6));
        assertEquals(17, row.getLong(7));
        assertEquals("{\"id\":3}", row.getString(8).toString());
        assertTrue(row.isNullAt(9)); // before = null
        assertEquals(1000, row.getTimestamp(11, 3).getMillisecond());
    }
}
