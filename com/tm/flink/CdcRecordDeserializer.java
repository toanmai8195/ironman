package com.tm.flink;

import java.nio.charset.StandardCharsets;
import org.apache.flink.api.common.typeinfo.TypeInformation;
import org.apache.flink.connector.kafka.source.reader.deserializer.KafkaRecordDeserializationSchema;
import org.apache.flink.util.Collector;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Chạy ngay trong source: byte[] của Kafka -> CdcRecord, kèm topic/partition/offset (chỉ có ở đây, các operator sau không thấy).
 * Message rỗng (tombstone) và message hỏng bị bỏ qua, message hỏng được log cảnh báo.
 */
public class CdcRecordDeserializer implements KafkaRecordDeserializationSchema<CdcRecord> {
    private static final Logger LOG = LoggerFactory.getLogger(CdcRecordDeserializer.class);

    @Override
    public void deserialize(ConsumerRecord<byte[], byte[]> record, Collector<CdcRecord> out) {
        if (record.value() == null || record.value().length == 0) {
            return; // tombstone
        }
        try {
            CdcEvent e = CdcEvent.fromJson(new String(record.value(), StandardCharsets.UTF_8));
            out.collect(CdcRecord.of(e, record.topic(), record.partition(), record.offset()));
        } catch (IllegalArgumentException ex) {
            LOG.warn("bỏ message lỗi {}[{}]@{}: {}", record.topic(), record.partition(), record.offset(), ex.getMessage());
        }
    }

    @Override
    public TypeInformation<CdcRecord> getProducedType() {
        return TypeInformation.of(CdcRecord.class);
    }
}
