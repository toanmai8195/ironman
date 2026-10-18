package com.tm.flink;

import java.util.HashMap;
import java.util.Map;
import org.apache.flink.streaming.api.datastream.DataStream;
import org.apache.flink.table.data.GenericRowData;
import org.apache.flink.table.data.RowData;
import org.apache.flink.table.data.StringData;
import org.apache.flink.table.data.TimestampData;
import org.apache.flink.table.runtime.typeutils.InternalTypeInfo;
import org.apache.hadoop.conf.Configuration;
import org.apache.iceberg.PartitionSpec;
import org.apache.iceberg.Schema;
import org.apache.iceberg.catalog.Catalog;
import org.apache.iceberg.catalog.Namespace;
import org.apache.iceberg.catalog.SupportsNamespaces;
import org.apache.iceberg.catalog.TableIdentifier;
import org.apache.iceberg.flink.CatalogLoader;
import org.apache.iceberg.flink.FlinkSchemaUtil;
import org.apache.iceberg.flink.TableLoader;
import org.apache.iceberg.flink.sink.FlinkSink;
import org.apache.iceberg.types.Types;

/** Bảng bronze trên Iceberg (REST catalog + S3FileIO trên MinIO): tạo bảng nếu chưa có, đổi CdcRecord thành dòng, ghi vào bảng. */
public final class IcebergBronze {
    public static final TableIdentifier TABLE = TableIdentifier.of("bronze", "cdc_events");

    /** Cột của bảng bronze: dữ liệu thô giữ nguyên + metadata Kafka/Debezium + thời điểm ghi. */
    public static final Schema SCHEMA = new Schema(
            Types.NestedField.required(1, "source_table", Types.StringType.get()),
            Types.NestedField.required(2, "op", Types.StringType.get()),
            Types.NestedField.required(3, "deleted", Types.BooleanType.get()),
            Types.NestedField.required(4, "source_ts_ms", Types.LongType.get()),
            Types.NestedField.required(5, "lsn", Types.LongType.get()),
            Types.NestedField.required(6, "kafka_topic", Types.StringType.get()),
            Types.NestedField.required(7, "kafka_partition", Types.IntegerType.get()),
            Types.NestedField.required(8, "kafka_offset", Types.LongType.get()),
            Types.NestedField.optional(9, "row_json", Types.StringType.get()),
            Types.NestedField.optional(10, "before_json", Types.StringType.get()),
            Types.NestedField.optional(11, "after_json", Types.StringType.get()),
            Types.NestedField.required(12, "ingest_ts", Types.TimestampType.withZone()));

    private IcebergBronze() {}

    public static Map<String, String> catalogProps(String restUri, String warehouse, String s3Endpoint,
                                                   String accessKey, String secretKey) {
        Map<String, String> p = new HashMap<>();
        p.put("uri", restUri);
        p.put("warehouse", warehouse);
        p.put("io-impl", "org.apache.iceberg.aws.s3.S3FileIO");
        p.put("s3.endpoint", s3Endpoint);
        p.put("s3.path-style-access", "true");
        p.put("s3.access-key-id", accessKey);
        p.put("s3.secret-access-key", secretKey);
        p.put("client.region", "us-east-1");
        return p;
    }

    public static CatalogLoader catalogLoader(Map<String, String> props) {
        return CatalogLoader.rest("rest", new Configuration(), props);
    }

    /** Idempotent: tạo namespace và bảng (partition theo ngày ghi) nếu chưa có. */
    public static void ensureTable(CatalogLoader loader) {
        Catalog catalog = loader.loadCatalog();
        SupportsNamespaces ns = (SupportsNamespaces) catalog;
        Namespace bronze = Namespace.of(TABLE.namespace().levels());
        if (!ns.namespaceExists(bronze)) {
            ns.createNamespace(bronze);
        }
        if (!catalog.tableExists(TABLE)) {
            catalog.createTable(TABLE, SCHEMA, PartitionSpec.builderFor(SCHEMA).day("ingest_ts").build());
        }
    }

    public static RowData toRow(CdcRecord r, long ingestTsMs) {
        return GenericRowData.of(
                StringData.fromString(r.sourceTable),
                StringData.fromString(r.op),
                r.deleted,
                r.tsMs,
                r.lsn,
                StringData.fromString(r.topic),
                r.partition,
                r.offset,
                str(r.row),
                str(r.before),
                str(r.after),
                TimestampData.fromEpochMillis(ingestTsMs));
    }

    /** Ghi vào bảng; Iceberg sink chỉ commit snapshot khi checkpoint hoàn tất. */
    public static void append(DataStream<CdcRecord> records, CatalogLoader loader) {
        DataStream<RowData> rows = records
                .map(r -> toRow(r, System.currentTimeMillis()))
                .returns(InternalTypeInfo.of(FlinkSchemaUtil.convert(SCHEMA)))
                .name("to-row");
        FlinkSink.forRowData(rows).tableLoader(TableLoader.fromCatalog(loader, TABLE)).append();
    }

    private static StringData str(String s) {
        return s == null ? null : StringData.fromString(s);
    }
}
