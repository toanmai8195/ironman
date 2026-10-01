# Ironman

Sandbox cá nhân để thử nghiệm **từng công nghệ Data Engineering một cách riêng lẻ**. Mỗi công nghệ nằm trong một thư mục độc lập, tự chứa đủ để chạy và xoá mà không ảnh hưởng phần còn lại.

> Đây không phải một hệ thống production hay một pipeline end-to-end. Mục tiêu là học, so sánh và ghi lại trải nghiệm thực tế với từng công cụ.

## Nguyên tắc

- **Chung hạ tầng, riêng thử nghiệm**: một Bazel module và một docker compose cho cả repo; mỗi thử nghiệm chỉ thêm service nó cần.
- **Tái lập được**: clone về chạy được bằng vài lệnh.
- **Ghi chép**: mỗi thử nghiệm có mục tiêu, cách chạy và nhận xét ngay trong README này hoặc README riêng.
- **Dùng xong bỏ được**: không coupling giữa các thử nghiệm (xoá thư mục + service tương ứng là xong).

## Cấu trúc

Layout theo [vision](../vision) / [thor](../thor): Bazel 8 (bzlmod) + rules_go + rules_oci.

```
ironman/
├── MODULE.bazel  BUILD.bazel  .bazelrc  .bazelversion   # Bazel module duy nhất
├── go.mod                                               # module com.tm/ironman
├── tools/rules/com_tm_container.bzl                     # macro com_tm_go_image: binary + OCI image
└── com/tm/
    ├── docker/ironman/docker-compose.yml                # compose chung
    └── <experiment>/                                    # mỗi thử nghiệm một thư mục, tự chứa code + config
        └── ...
```

Image Go: `com.tm.go.<name>:v1.0.0`; mỗi `com_tm_go_image` sinh `<name>`, `<name>_image`, `<name>_docker`.

## Danh sách thử nghiệm

| Thư mục | Công nghệ | Mục tiêu | Trạng thái |
|---------|-----------|----------|------------|
| [`com/tm/debezium`](com/tm/debezium) | Postgres + Debezium + Kafka + Go consumer | Bắt thay đổi Postgres thành event CDC, consume và liệt kê bằng service Go | `done` |
| [`com/tm/flink`](com/tm/flink/SETUP.md) | Flink (Java) + Iceberg | pg → Debezium → Kafka → Flink → Iceberg (bronze): làm phẳng CDC, checkpoint/savepoint, event time, application mode. Chạy: `com/tm/flink/build.sh` rồi `docker compose ... --profile flink up -d --build`; query bảng bằng DBeaver qua StarRocks (`localhost:19030`) | `done` |

Trạng thái: `idea` → `wip` → `done` / `dropped`

### 1. Debezium: Postgres → Debezium → Kafka → Go

Thư mục `com/tm/debezium/`: `consumer/` (service Go), `connector/` (config + script đăng ký Debezium), `postgres/` (schema/seed). Chi tiết setup, config và xử lý sự cố: [`SETUP.md`](com/tm/debezium/SETUP.md).

```
postgres (wal_level=logical) ──Debezium──► kafka: ironman.public.{customers,orders} ──► cdc-consumer (Go)
```

```bash
# 1. Build + load image consumer vào Docker local (Apple Silicon; máy x86 dùng linux-amd64)
bazel run --config=linux-arm64 //com/tm/debezium/consumer:cdc_consumer_docker
bazel run --config=linux-arm64 //com/tm/debezium/updater:pg_updater_docker   # sinh 1 update/giây vào Postgres

# 2. Dựng stack (postgres, kafka, debezium, đăng ký connector, consumer)
docker compose -f com/tm/docker/ironman/docker-compose.yml up -d

# 3. Tạo thay đổi rồi xem event
docker exec ironman-postgres psql -U ironman -d ironman -c "UPDATE orders SET status='PAID' WHERE id=1"
docker logs -f ironman-cdc-consumer

# Dọn dẹp (xoá cả volume)
docker compose -f com/tm/docker/ironman/docker-compose.yml down -v
```

- Event gồm `opName` (`snapshot` / `create` / `update` / `delete`), `table`, `before`, `after`, `lsn`, `offset`. Lần đầu sẽ thấy các dòng `snapshot` từ dữ liệu seed trong `com/tm/debezium/postgres/init.sql`.
- Port host: Postgres `5434`, Kafka `39092`, Debezium REST `8084` (khác vision/thor để chạy song song).
- Consumer chỉ in log mỗi event; offset được commit theo consumer group.
- Test: `bazel test //...`

## Ứng viên dự kiến

Danh sách các hướng muốn thử (chỉnh sửa tuỳ ý):

- **Ingestion / Streaming**: Kafka, Redpanda, Debezium, Flink
- **Orchestration**: Airflow, Dagster, Prefect
- **Transformation**: dbt, SQLMesh, Spark
- **Storage / Table format**: Iceberg, Delta Lake, Hudi, Parquet
- **Query engine / Warehouse**: DuckDB, Trino, ClickHouse, BigQuery
- **Data quality / Observability**: Great Expectations, Soda, OpenLineage

## Yêu cầu

- Bazelisk (đọc `.bazelversion` = 8.7.0), Docker & Docker Compose, Go (chỉ để `go mod tidy` / IDE)

## Thêm thử nghiệm mới

1. Code + config vào `com/tm/<experiment>/`; service Go dùng macro `com_tm_go_image`.
2. Thêm service vào compose chung (`com/tm/docker/ironman/docker-compose.yml`), chọn port host không trùng.
3. Thêm dependency Go: `go get <module>@<version>` → `bazel mod tidy` → `bazel run //:gazelle`.
4. Thêm một dòng vào bảng [Danh sách thử nghiệm](#danh-sách-thử-nghiệm).

## Ghi chú

- Không commit secret/credential. Dùng `.env` (đã nằm trong `.gitignore`) và cung cấp `.env.example` nếu cần.
- Dữ liệu lớn nên sinh ra bằng script thay vì commit trực tiếp.
