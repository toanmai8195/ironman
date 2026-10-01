# Flink: pg → Debezium → Kafka → Flink → Iceberg (bronze)

```
postgres ──Debezium──► kafka: ironman.public.{customers,orders} ──► Flink job (cdc-flatten) ─┬─► Iceberg bronze.cdc_events (MinIO)
                                                                                              └─► đếm theo window event-time (in ra log)
```

## Các bước đã làm

| Bước | Nội dung | Khái niệm |
|---|---|---|
| 1 | Đọc topic CDC từ Kafka | Kafka source, parse envelope Debezium |
| 2 | Làm phẳng thành cột cố định + metadata Kafka (`topic[partition]@offset`, `lsn`, `deleted`) | map/filter, deserializer trong source |
| 3 | Chạy trên cluster, checkpoint lưu MinIO, kill TaskManager vẫn phục hồi | checkpoint, restart strategy |
| 4 | Ghi file JSON Lines lên S3 | FileSink, commit theo checkpoint |
| 5 | Ghi vào Iceberg (REST catalog, Parquet trên MinIO) | table format, snapshot, commit theo checkpoint |
| 6 | Event time + watermark, window 1 phút, event trễ vào side output | event time, allowed lateness |
| 7 | Application mode, savepoint | cách chạy gần prod |

Mỗi bước xong thì dọn code thừa của bước cũ nên repo chỉ giữ code của trạng thái cuối (bước 4 đã được thay bằng Iceberg ở bước 5). Prometheus chưa làm, để khi vào dự án thực tế.

## Chạy

Từ thư mục gốc repo:

```bash
F=com/tm/docker/ironman/docker-compose.yml

# 1. Build fat jar -> com/tm/flink/dist/cdc-flatten.jar, và load image pg-updater (sinh 1 update/giây vào Postgres)
com/tm/flink/build.sh
bazel run --config=linux-arm64 //com/tm/debezium/updater:pg_updater_docker

# 2. Dựng stack: Postgres, Kafka, Debezium + Flink (JobManager, TaskManager) + MinIO + Iceberg REST.
#    Application mode: JobManager tự chạy job CdcFlatten, không cần nộp tay.
docker compose -f $F --profile flink up -d --build

# 3. Xem: Flink UI http://localhost:18081, MinIO http://localhost:19001 (ironman / ironman-secret),
#    query bảng Iceberg bằng DBeaver -> StarRocks localhost:19030 (xem mục Query dữ liệu Iceberg)
#    Kết quả đếm theo window và event trễ in ở log TaskManager:
docker logs -f ironman-flink-taskmanager

# 4. Thay đổi trong Postgres đã có sẵn: service pg-updater đổi trạng thái 1 đơn hàng mỗi giây (1 rps).
#    Muốn tự tạo thay đổi: docker exec ironman-postgres psql -U ironman -d ironman -c "UPDATE orders SET status='PAID' WHERE id=1"

# Dọn dẹp
docker compose -f $F --profile flink down -v
```

Cấu hình job qua biến môi trường của service `flink-jobmanager`: `WINDOW_SEC` (mặc định 60), `WATERMARK_DELAY_SEC` (5), `ALLOWED_LATENESS_SEC` (30), `SKIP_SNAPSHOT`.

## Query dữ liệu Iceberg

Iceberg REST catalog và MinIO không có UI xem bảng (MinIO console chỉ thấy file Parquet/metadata). Có hai cách query bằng SQL:

### Cách 1: StarRocks + DBeaver (có UI)

Compose có sẵn StarRocks (profile `flink`) với external catalog `ice` trỏ vào Iceberg REST. StarRocks nói giao thức MySQL nên DBeaver (hoặc bất kỳ client MySQL nào) kết nối được.

DBeaver: New Connection → **MySQL** → Host `localhost`, Port `19030`, User `root`, để trống Password → Test Connection. Bảng nằm ở `ice.bronze.cdc_events` (luôn ghi đủ `catalog.database.table`). Mình chưa mở DBeaver để thử, nhưng đã query thành công qua giao thức MySQL của StarRocks.

```bash
# Hoặc dùng client trong container (client mysql 9.x trên máy host không kết nối được: đã bỏ plugin mysql_native_password)
docker exec -it ironman-starrocks mysql -h127.0.0.1 -P9030 -uroot
```

```sql
SHOW CATALOGS;                          -- ice (Iceberg)
SHOW TABLES FROM ice.bronze;            -- cdc_events
SELECT source_table, op, COUNT(*) FROM ice.bronze.cdc_events GROUP BY source_table, op;

-- Trạng thái hiện tại của orders (event mới nhất theo lsn của mỗi id, bỏ dòng đã xoá)
SELECT id, status FROM (
  SELECT get_json_string(row_json, '$.id') AS id, get_json_string(row_json, '$.status') AS status, deleted,
         row_number() OVER (PARTITION BY get_json_string(row_json, '$.id') ORDER BY lsn DESC) AS rn
  FROM ice.bronze.cdc_events WHERE source_table = 'public.orders') t
WHERE rn = 1 AND NOT deleted ORDER BY id;
```

Lưu ý:
- **StarRocks cache metadata Iceberg** nên có thể thấy snapshot cũ. Muốn thấy dữ liệu mới nhất: `REFRESH EXTERNAL TABLE ice.bronze.cdc_events;`. Đã quan sát: trước khi refresh một đơn hiện trạng thái cũ, sau refresh khớp đúng với Postgres.
- Lần chạy query đầu tiên sau khi khởi động có lần treo hơn 2 phút (phải `KILL`), chạy lại thì xong trong vài giây. Chưa rõ nguyên nhân (nghi BE nguội). Khi thử nên đặt `SET query_timeout=60;`.
- Image StarRocks khoảng 8GB và ăn nhiều RAM; không cần thì bỏ: `docker compose ... --profile flink up -d --scale starrocks=0 --scale starrocks-init=0`.

### Cách 2: DuckDB (nhẹ, không cần container)

Trỏ thẳng vào REST catalog, không đụng job đang chạy. Application mode chỉ chạy một job nên không dùng Flink SQL client để query được.

```bash
python3 -m venv .venv && .venv/bin/pip install duckdb      # .venv đã nằm trong .gitignore
.venv/bin/python
```

```python
import duckdb
c = duckdb.connect()
c.execute("INSTALL iceberg; LOAD iceberg; INSTALL httpfs; LOAD httpfs;")
# MinIO từ máy host: cổng 19000, path-style
c.execute("""CREATE SECRET s3 (TYPE S3, KEY_ID 'ironman', SECRET 'ironman-secret', ENDPOINT 'localhost:19000',
             URL_STYLE 'path', USE_SSL false, REGION 'us-east-1')""")
c.execute("ATTACH 'warehouse' AS ice (TYPE ICEBERG, ENDPOINT 'http://localhost:18181', AUTHORIZATION_TYPE 'NONE')")

c.sql("SELECT source_table, op, count(*) FROM ice.bronze.cdc_events GROUP BY ALL ORDER BY 1, 2").show()
```

**Trạng thái hiện tại** của `orders` bằng DuckDB (silver trong một câu SQL: event mới nhất theo `lsn` của mỗi `id`, bỏ dòng đã xoá):

```sql
SELECT json_extract_string(row_json, '$.id')     AS id,
       json_extract_string(row_json, '$.status') AS status
FROM ice.bronze.cdc_events
WHERE source_table = 'public.orders'
QUALIFY row_number() OVER (PARTITION BY json_extract_string(row_json, '$.id') ORDER BY lsn DESC) = 1
   AND NOT deleted
ORDER BY id;
```

**Lịch sử một đơn** (mỗi dòng là một lần đổi trạng thái):

```sql
SELECT kafka_partition, kafka_offset, op, json_extract_string(after_json, '$.status') AS status, ingest_ts
FROM ice.bronze.cdc_events
WHERE source_table = 'public.orders' AND json_extract_string(row_json, '$.id') = '1'
ORDER BY lsn DESC LIMIT 10;
```

Đã đối chiếu: sau khi dừng `pg-updater` và đợi một checkpoint, kết quả câu "trạng thái hiện tại" khớp đúng với `SELECT id, status FROM orders` ở Postgres. Khi updater đang chạy thì bronze luôn **chậm hơn** Postgres tối đa một chu kỳ checkpoint (10s), vì Iceberg chỉ commit khi checkpoint hoàn tất.

Cột `before_json` của `update` là `NULL` trừ khi bảng bật `REPLICA IDENTITY FULL`.

Ngoài DuckDB, Trino/Spark/PyIceberg cũng đọc được qua cùng REST catalog (`http://localhost:18181`). Xem snapshot/file ở tầng thấp:

```bash
curl -s localhost:18181/v1/namespaces/bronze/tables/cdc_events | python3 -m json.tool | grep -E "total-records|added-records"
docker run --rm --network ironman_default --entrypoint sh \
  minio/mc@sha256:a7fe349ef4bd8521fb8497f55c6042871b2ae640607cf99d9bede5e9bdf11727 \
  -c 'mc alias set l http://minio:9000 ironman ironman-secret >/dev/null; mc ls --recursive l/warehouse'
```

### Bảng `bronze.cdc_events`

Mỗi event CDC là **một dòng** (nhật ký thay đổi, append-only), không phải bản sao của bảng nguồn:

| Cột | Ý nghĩa |
|---|---|
| `source_table`, `op` | Bảng nguồn; `r` snapshot, `c` insert, `u` update, `d` delete |
| `deleted` | `true` nếu `op = d` |
| `source_ts_ms`, `lsn` | Thời điểm và vị trí trong WAL của Postgres |
| `kafka_topic`, `kafka_partition`, `kafka_offset` | Vị trí trong Kafka (truy vết, dedup) |
| `row_json` | Dòng sau thay đổi (hoặc dòng trước nếu là delete) |
| `before_json`, `after_json` | Bản gốc từ Debezium |
| `ingest_ts` | Lúc Flink ghi (partition theo ngày) |

Trạng thái hiện tại của một bảng (lấy event mới nhất theo `lsn` của mỗi `id`, bỏ dòng `deleted`) tính ở tầng silver, chưa làm. Muốn event `delete` mang đủ cột cũ thì bật `ALTER TABLE <bảng> REPLICA IDENTITY FULL` ở Postgres.

## Thử phục hồi lỗi

**Kill TaskManager** (checkpoint, 10s/lần):

```bash
docker kill ironman-flink-taskmanager      # rồi tạo thêm thay đổi trong Postgres
docker start ironman-flink-taskmanager     # job tự restore từ checkpoint gần nhất
```

Đã quan sát: job restore từ `s3://flink/checkpoints/<jobId>/chk-N`, chỉ xử lý event phát sinh lúc TaskManager chết, không đọc lại từ đầu topic (offset Kafka nằm trong checkpoint). JobManager phải đợi heartbeat timeout (mặc định 50s) mới biết TaskManager chết.

**Savepoint** (dừng cluster có chủ đích, ví dụ nâng cấp job):

```bash
JID=$(curl -s localhost:18081/jobs/overview | python3 -c "import sys,json;print(json.load(sys.stdin)['jobs'][0]['jid'])")
docker exec ironman-flink-jobmanager flink savepoint $JID          # in ra s3://flink/savepoints/savepoint-...
docker compose -f $F --profile flink stop flink-jobmanager flink-taskmanager
SAVEPOINT_PATH=s3://flink/savepoints/savepoint-... docker compose -f $F --profile flink up -d flink-jobmanager flink-taskmanager
```

Đã quan sát: job `restored` từ savepoint, bảng Iceberg chỉ tăng đúng số event phát sinh lúc cluster tắt (không trùng dòng cũ). Không truyền `SAVEPOINT_PATH` thì job bắt đầu mới và đọc lại từ đầu topic.

## Event time và event trễ

Watermark tính từ `ts_ms` của DB nguồn (không phải lúc Flink nhận). Đã quan sát: các window `WINDOW [16:02:40, ...)` nằm đúng thời điểm của event cũ khi job đọc lại topic, và một event giả có `ts_ms` lùi 5 phút bị đẩy vào side output (`LATE ...`). Tự thử bằng cách bắn message vào topic với `ts_ms` cũ:

```bash
echo '{"before":null,"after":{"id":99},"source":{"schema":"public","table":"orders","lsn":1},"op":"c","ts_ms":1}' | \
  docker exec -i ironman-kafka /opt/kafka/bin/kafka-console-producer.sh --bootstrap-server kafka:9092 --topic ironman.public.orders
```

Window chỉ đóng khi có event mới đẩy watermark đi lên, nên hệ thống ít event thì kết quả ra chậm.

## Cấu hình và build

- Checkpoint, restart, S3, savepoint nằm ở `FLINK_PROPERTIES` trong compose, không nằm trong code job.
- Image Flink tuỳ biến: `docker/Dockerfile` (thêm `iceberg-flink-runtime`, `iceberg-aws-bundle`, Hadoop client).
- Fat jar chỉ chứa code job, connector Kafka và Jackson. Class do image cung cấp không đóng vào jar (`deploy_env` trong `BUILD.bazel`).
- Application mode: cả JobManager và TaskManager đều phải mount jar vào `/opt/flink/usrlib`.
- Test: `bazel test //com/tm/flink/...`
