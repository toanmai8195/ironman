package com.tm.flink;

import java.time.Duration;
import java.time.Instant;
import org.apache.flink.api.common.eventtime.WatermarkStrategy;
import org.apache.flink.api.common.typeinfo.TypeInformation;
import org.apache.flink.connector.kafka.source.KafkaSource;
import org.apache.flink.connector.kafka.source.enumerator.initializer.OffsetsInitializer;
import org.apache.flink.streaming.api.datastream.DataStream;
import org.apache.flink.streaming.api.datastream.SingleOutputStreamOperator;
import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;
import org.apache.flink.streaming.api.windowing.assigners.TumblingEventTimeWindows;
import org.apache.flink.util.OutputTag;
import org.apache.iceberg.flink.CatalogLoader;

/**
 * Event CDC -> CdcRecord (cột cố định + metadata Kafka) -> bảng Iceberg bronze.cdc_events (REST catalog, MinIO).
 *
 * <pre>
 * Kafka ──► source + deserializer + watermark(ts_ms) ──► filter ──┬─► toRow ──► Iceberg FlinkSink
 *                                                                 └─► keyBy(bảng|op) ─► window event-time ─┬─► print (đếm)
 *                                                                                                          └─► print (LATE: quá trễ)
 * </pre>
 *
 * Event time = ts_ms của DB nguồn (không phải lúc Flink nhận). Watermark = event time lớn nhất đã thấy trừ
 * WATERMARK_DELAY_SEC: Flink tin rằng sẽ không còn event nào cũ hơn mốc đó. Window đóng khi watermark vượt cuối window,
 * event đến muộn thêm ALLOWED_LATENESS_SEC vẫn được cộng và phát lại kết quả; muộn hơn nữa thì vào side output.
 * Window chỉ đóng khi có event mới đẩy watermark đi lên (hệ thống ít event thì kết quả ra chậm).
 *
 * Iceberg sink chỉ commit snapshot khi checkpoint hoàn tất, nên dữ liệu xuất hiện trong bảng theo từng checkpoint.
 * Giao hàng at-least-once: event trùng (sau restart) được xử lý ở silver, không dedup ở bronze.
 *
 * Chạy trên cluster Flink (xem com/tm/flink/SETUP.md). Checkpoint, state backend và restart strategy cấu hình ở
 * flink-conf (FLINK_PROPERTIES trong compose), không nằm trong code job.
 * Biến môi trường (đọc ở process nộp job): KAFKA_BOOTSTRAP, KAFKA_TOPICS, ICEBERG_REST_URI, ICEBERG_WAREHOUSE,
 * S3_ENDPOINT, S3_ACCESS_KEY, S3_SECRET_KEY, SKIP_SNAPSHOT=true để bỏ các event op=r,
 * WATERMARK_DELAY_SEC, WINDOW_SEC, ALLOWED_LATENESS_SEC.
 */
public final class CdcFlatten {
    public static void main(String[] args) throws Exception {
        String bootstrap = env("KAFKA_BOOTSTRAP", "kafka:9092");
        String topics = env("KAFKA_TOPICS", "ironman.public.customers,ironman.public.orders");
        CatalogLoader catalog = IcebergBronze.catalogLoader(IcebergBronze.catalogProps(
                env("ICEBERG_REST_URI", "http://iceberg-rest:8181"),
                env("ICEBERG_WAREHOUSE", "s3://warehouse/"),
                env("S3_ENDPOINT", "http://minio:9000"),
                env("S3_ACCESS_KEY", "ironman"),
                env("S3_SECRET_KEY", "ironman-secret")));
        IcebergBronze.ensureTable(catalog);

        long watermarkDelaySec = Long.parseLong(env("WATERMARK_DELAY_SEC", "5"));
        long windowSec = Long.parseLong(env("WINDOW_SEC", "60"));
        long allowedLatenessSec = Long.parseLong(env("ALLOWED_LATENESS_SEC", "30"));
        boolean skipSnapshot = Boolean.parseBoolean(env("SKIP_SNAPSHOT", "false"));

        StreamExecutionEnvironment senv = StreamExecutionEnvironment.getExecutionEnvironment();
        senv.setParallelism(1);

        KafkaSource<CdcRecord> source = KafkaSource.<CdcRecord>builder()
                .setBootstrapServers(bootstrap)
                .setTopics(topics.split(","))
                .setGroupId("flink-cdc-flatten")
                .setStartingOffsets(OffsetsInitializer.earliest())
                .setDeserializer(new CdcRecordDeserializer())
                .build();

        // Watermark tính riêng cho từng partition Kafka rồi lấy min; partition im quá 10s bị coi là idle để không chặn cả job.
        DataStream<CdcRecord> records = senv
                .fromSource(source, WatermarkStrategy
                        .<CdcRecord>forBoundedOutOfOrderness(Duration.ofSeconds(watermarkDelaySec))
                        .withTimestampAssigner((r, ts) -> r.tsMs)
                        .withIdleness(Duration.ofSeconds(10)), "kafka-cdc")
                .filter(r -> !skipSnapshot || !"r".equals(r.op));
        IcebergBronze.append(records, catalog);

        OutputTag<CdcRecord> late = new OutputTag<>("late", TypeInformation.of(CdcRecord.class));
        SingleOutputStreamOperator<String> counts = records
                .keyBy(WindowCount::key)
                .window(TumblingEventTimeWindows.of(Duration.ofSeconds(windowSec)))
                .allowedLateness(Duration.ofSeconds(allowedLatenessSec))
                .sideOutputLateData(late)
                .process(new WindowCount()).name("window-count");
        counts.print();
        counts.getSideOutput(late)
                .map(r -> "LATE " + WindowCount.key(r) + " ts=" + Instant.ofEpochMilli(r.tsMs) + " row=" + r.row)
                .print();

        senv.execute("cdc-flatten");
    }

    private static String env(String key, String def) {
        String v = System.getenv(key);
        return v == null || v.isEmpty() ? def : v;
    }
}
