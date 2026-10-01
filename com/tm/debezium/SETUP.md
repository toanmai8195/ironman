# Debezium: setup

Thử nghiệm CDC: thay đổi trong Postgres được Debezium đọc từ WAL, đẩy lên Kafka, rồi service Go consume và liệt kê.

```
postgres ──WAL (pgoutput)──► debezium (Kafka Connect) ──► kafka ──► cdc-consumer (Go) ──► log
```

## Thành phần

| Thư mục | Nội dung |
|---------|----------|
| `postgres/init.sql` | Schema + seed: `public.customers`, `public.orders`. Chỉ chạy lần đầu tạo volume. |
| `connector/connector.json` | Config connector Debezium Postgres. |
| `connector/register.sh` | Đăng ký connector (idempotent) và chờ RUNNING. |
| `updater/` | Service Go `pg-updater`: mỗi giây (`RATE_PER_SEC`) đổi trạng thái 1 đơn hàng ngẫu nhiên, tạo luồng CDC liên tục. |
| `consumer/` | Service Go: Kafka consumer group → parse envelope → in log. |
| `../docker/ironman/docker-compose.yml` | Compose chung (postgres, kafka, debezium, consumer). |

## Yêu cầu

- Docker + Docker Compose
- Bazelisk (đọc `.bazelversion` = 8.7.0 ở thư mục gốc)
- Port trống trên host: `5434` (Postgres), `39092` (Kafka), `8084` (Debezium REST)

## Chạy

Mọi lệnh chạy từ thư mục gốc repo.

```bash
# 1. Build image consumer và updater, load vào Docker local (máy x86: --config=linux-amd64)
bazel run --config=linux-arm64 //com/tm/debezium/consumer:cdc_consumer_docker
bazel run --config=linux-arm64 //com/tm/debezium/updater:pg_updater_docker

# 2. Dựng stack
docker compose -f com/tm/docker/ironman/docker-compose.yml up -d
```

Thứ tự khởi động do `depends_on` đảm bảo:

1. `postgres` và `kafka` healthy
2. `kafka-init` tạo topic `ironman.public.customers` và `ironman.public.orders` (3 partition)
3. `debezium` (Kafka Connect) healthy
4. `debezium-register` PUT connector, chờ connector + task RUNNING rồi thoát (Exit 0 là bình thường)
5. `cdc-consumer` bắt đầu đọc từ offset đầu (`OffsetOldest`)

> Compose đặt `pull_policy: never` cho `cdc-consumer`. Nếu chưa chạy bước 1, `up` sẽ báo không tìm thấy image `com.tm.go.cdc_consumer:v1.0.0`.

## Kiểm tra

```bash
F=com/tm/docker/ironman/docker-compose.yml

# Trạng thái container
docker compose -f $F ps -a

# Connector và task đều phải RUNNING
curl -s localhost:8084/connectors/ironman-pg/status

# Tạo thay đổi
docker exec ironman-postgres psql -U ironman -d ironman \
  -c "UPDATE orders SET status='PAID' WHERE id=1" \
  -c "DELETE FROM orders WHERE id=2"

# Xem event qua log của service Go
docker logs -f ironman-cdc-consumer

# Xem message thô trên Kafka
docker exec ironman-kafka /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server kafka:9092 --topic ironman.public.orders --from-beginning
```

Kết quả mong đợi: lần đầu có các event `snapshot` (op `r`) cho dữ liệu seed, sau đó `update` (`u`) và `delete` (`d`) cho các lệnh trên. `create` (`c`) xuất hiện khi `INSERT`.

## Cấu hình chính

### Postgres

Compose chạy Postgres với `wal_level=logical`, `max_replication_slots=10`, `max_wal_senders=10`. Đây là điều kiện bắt buộc để Debezium đọc WAL bằng logical decoding.

### Connector (`connector/connector.json`)

| Key | Ý nghĩa |
|-----|---------|
| `plugin.name=pgoutput` | Plugin decoding có sẵn trong Postgres, không cần cài thêm. |
| `slot.name=ironman_cdc` | Replication slot Debezium dùng để giữ vị trí đọc WAL. |
| `publication.name`, `publication.autocreate.mode=filtered` | Debezium tự tạo publication chỉ gồm các bảng trong `table.include.list`. |
| `table.include.list` | `public.customers,public.orders`. |
| `topic.prefix=ironman` | Topic tên `<prefix>.<schema>.<table>`, ví dụ `ironman.public.orders`. |
| `snapshot.mode=initial` | Snapshot toàn bộ dữ liệu hiện có một lần, rồi chuyển sang đọc WAL. |
| `decimal.handling.mode=string` | `NUMERIC` ra dạng chuỗi, tránh mất độ chính xác (ví dụ `"150000.00"`). |
| `*.converter.schemas.enable=false` | JSON gọn, không kèm schema. Consumer Go phụ thuộc vào dạng này. |
| `tombstones.on.delete=false` | Không gửi thêm message null sau event delete. |

Sửa file rồi chạy lại để cập nhật connector:

```bash
docker compose -f com/tm/docker/ironman/docker-compose.yml run --rm debezium-register
```

### Consumer (biến môi trường)

| Biến | Mặc định | Ghi chú |
|------|----------|---------|
| `KAFKA_BROKERS` | `localhost:39092` | Trong compose là `kafka:9092`. |
| `KAFKA_TOPICS` | `ironman.public.customers,ironman.public.orders` | Topic phải tồn tại trước. |
| `KAFKA_GROUP` | `ironman-cdc-consumer` | Đổi tên group để đọc lại từ đầu. |

Chạy consumer ngoài Docker (dùng listener `localhost:39092`):

```bash
bazel run //com/tm/debezium/consumer:cdc_consumer
```

## Format event

Value của message là envelope Debezium. Consumer Go parse và in một dòng log cho mỗi event:

```
level=INFO msg=cdc op=update table=public.orders topic=ironman.public.orders partition=0 offset=1 before=map[] after="map[amount:150000.00 id:1 status:PAID ...]"
```

`before` chỉ có giá trị khi bảng bật `REPLICA IDENTITY FULL`. Mặc định (khoá chính) event `update` có `before` rỗng, còn `delete` chỉ chứa khoá chính. Để thử: `ALTER TABLE public.orders REPLICA IDENTITY FULL;`.

## Dọn dẹp và reset

```bash
# Dừng, giữ dữ liệu
docker compose -f com/tm/docker/ironman/docker-compose.yml down

# Dừng và xoá sạch volume (Postgres, Kafka); lần sau init.sql chạy lại
docker compose -f com/tm/docker/ironman/docker-compose.yml down -v
```

Chỉ muốn consumer đọc lại từ đầu: đổi `KAFKA_GROUP` hoặc xoá group:

```bash
docker exec ironman-kafka /opt/kafka/bin/kafka-consumer-groups.sh \
  --bootstrap-server kafka:9092 --delete --group ironman-cdc-consumer
```

## Xử lý sự cố

| Triệu chứng | Nguyên nhân thường gặp | Cách xử lý |
|-------------|------------------------|------------|
| `pull access denied ... cdc_consumer` | Chưa load image vào Docker. | Chạy bước 1 ở mục [Chạy](#chạy). |
| `debezium-register` Exit 1 | Task FAILED (sai kết nối Postgres, thiếu `wal_level=logical`). | Xem `docker logs ironman-debezium` và `curl localhost:8084/connectors/ironman-pg/status`. |
| Log consumer không có dòng `cdc` | Consumer chưa join group hoặc connector chưa RUNNING. | `docker logs ironman-cdc-consumer`; kiểm tra status connector. |
| Sửa `init.sql` nhưng không có hiệu lực | Script chỉ chạy khi volume còn trống. | `down -v` rồi `up -d` lại. |
| Log consumer: `bỏ qua message lỗi` | Value không phải envelope JSON dạng schemas-disabled. | Kiểm tra `*.converter.schemas.enable=false`. |
| Ổ đĩa Docker đầy dần | Replication slot giữ WAL khi connector dừng lâu. | Xoá connector rồi xoá slot: `SELECT pg_drop_replication_slot('ironman_cdc');` |

Xem slot đang giữ bao nhiêu WAL:

```bash
docker exec ironman-postgres psql -U ironman -d ironman -c \
  "SELECT slot_name, active, pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn)) AS retained FROM pg_replication_slots"
```

## Test

```bash
bazel test //com/tm/debezium/...
```

Các test hiện có là unit test cho parse envelope. Luồng end-to-end kiểm tra bằng tay theo mục [Kiểm tra](#kiểm-tra).
