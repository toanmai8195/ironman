# Image Flink cho thử nghiệm: thêm jar Iceberg (sink), AWS bundle (S3FileIO) và Hadoop client (Iceberg Flink cần).
# Connector Kafka nằm trong fat jar của job nên không thêm ở đây. Version pin theo URL Maven Central.
FROM flink:1.20.2-scala_2.12-java17

ARG MAVEN=https://repo1.maven.org/maven2
RUN set -eux; cd /opt/flink/lib; \
    for u in \
      org/apache/iceberg/iceberg-flink-runtime-1.20/1.9.2/iceberg-flink-runtime-1.20-1.9.2.jar \
      org/apache/iceberg/iceberg-aws-bundle/1.9.2/iceberg-aws-bundle-1.9.2.jar \
      org/apache/hadoop/hadoop-client-api/3.3.6/hadoop-client-api-3.3.6.jar \
      org/apache/hadoop/hadoop-client-runtime/3.3.6/hadoop-client-runtime-3.3.6.jar; do \
      curl -fsSLO "$MAVEN/$u"; \
    done
