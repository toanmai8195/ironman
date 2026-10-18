# Ironman: setup toàn bộ pipeline

Chạy và kiểm tra pipeline từ đầu đến cuối:

```
pg-updater (Go)         Postgres            Debezium          Kafka                    Flink (Java)             Iceberg (MinIO)        Query
1 UPDATE / giây  ─────►  orders      ─WAL─►  connector  ─────►  ironman.public.*  ─────►  cdc-flatten    ─────►  bronze.cdc_events  ─►  StarRocks / DBeaver
                                                                                         (checkpoint 10s)        (Parquet + REST catalog)   DuckDB
```

Chi tiết từng phần: [`com/tm/debezium/SETUP.md`](com/tm/debezium/SETUP.md) (Postgres → Kafka) và [`com/tm/flink/SETUP.md`](com/tm/flink/SETUP.md) (Flink → Iceberg, savepoint, event time).

## 1. Yêu cầu

- Docker + Docker Compose. Nên cấp cho Docker nhiều RAM (StarRocks nặng, image ~8GB).
- Bazelisk (đọc `.bazelversion` = 8.7.0 ở thư mục gốc). Lần build Java đầu tiên chậm vì tải JDK và dependency, các lần sau có cache.
- Cổng trống trên máy: `5434` Postgres · `39092` Kafka · `8084` Debezium · `18081` Flink UI · `18181` Iceberg REST · `19000/19001` MinIO · `19030/18030` StarRocks.

Mọi lệnh bên dưới chạy từ thư mục gốc repo.

## 2. Build

```bash
# Máy x86 thay linux-arm64 bằng linux-amd64
bazel run --config=linux-arm64 //com/tm/debezium/updater:pg_updater_docker     # service update Postgres
bazel run --config=linux-arm64 //com/tm/flink:cdc_flatten_docker              # image Flink: base Flink + jar Iceberg/Hadoop + job (JobManager và TaskManager dùng chung)
```

Job Flink được đóng vào image `com.tm.flink.cdc_flatten:v1.0.0`. Mỗi lần sửa code job phải build lại image rồi tạo lại container `flink-jobmanager`/`flink-taskmanager` (compose không tự build).

## 3. Chạy

```bash
F=com/tm/docker/ironman/docker-compose.yml
docker compose -f $F --profile flink up -d
```

Đợi khoảng 2 phút rồi kiểm tra:

```bash
docker compose -f $F --profile flink ps -a
```

Mong đợi: `ironman-starrocks` và `ironman-iceberg-rest` ở trạng thái `healthy`; `kafka-init`, `debezium-register`, `minio-init`, `starrocks-init` thoát với `Exited (0)` (bình thường, là các job chạy một lần); các service còn lại `Up`.

Thứ tự khởi động do `depends_on` đảm bảo: Postgres, Kafka → tạo topic → Debezium → đăng ký connector; MinIO → tạo bucket → Iceberg REST → Flink JobManager (tự chạy job `CdcFlatten` ở application mode) → TaskManager; StarRocks → tạo catalog `ice`.

## 4. Kiểm tra từng chặng

Đi từ đầu pipeline xuống, mỗi chặng xác nhận dữ liệu đã đến được.

### 4.1. Service update Postgres

```bash
docker logs --tail 3 ironman-pg-updater
# level=INFO msg=update orderId=1 from=NEW to=PAID total=42
```

Mỗi giây một dòng. Đổi tốc độ bằng `RATE_PER_SEC` của service `pg-updater` trong compose.

```bash
docker exec ironman-postgres psql -U ironman -d ironman -c "SELECT id, status FROM orders ORDER BY id"
```

### 4.2. Debezium (CDC)

```bash
curl -s localhost:8084/connectors/ironman-pg/status      # connector và task đều "RUNNING"
```

### 4.3. Kafka

```bash
# Message CDC thô của 1 thay đổi: before / after / source / op
docker exec ironman-kafka /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server kafka:9092 --topic ironman.public.orders --from-beginning --timeout-ms 5000 | tail -1
```

Muốn xem event CDC dạng log: bật thêm consumer Go của thử nghiệm Debezium (không nằm trên đường tới Flink): `bazel run --config=linux-arm64 //com/tm/debezium/consumer:cdc_consumer_docker`, rồi `docker compose -f $F --profile consumer up -d cdc-consumer` và `docker logs --tail 3 ironman-cdc-consumer`.

### 4.4. Flink

- Flink UI: http://localhost:18081 → job `cdc-flatten` phải `RUNNING`.
- Checkpoint (10 giây/lần) phải hoàn tất và không lỗi:

```bash
JID=$(curl -s localhost:18081/jobs/overview | python3 -c "import sys,json;print(json.load(sys.stdin)['jobs'][0]['jid'])")
curl -s localhost:18081/jobs/$JID/checkpoints | python3 -c "import sys,json;c=json.load(sys.stdin)['counts'];print('completed',c['completed'],'failed',c['failed'])"
```

- Kết quả đếm theo window event-time và event trễ in ở log TaskManager: `docker logs ironman-flink-taskmanager | grep -E "^(WINDOW|LATE)"`. Window mặc định 60 giây.

### 4.5. Iceberg

Iceberg chỉ commit khi checkpoint hoàn tất, nên mỗi checkpoint có dữ liệu là một snapshot.

```bash
# Số dòng tích luỹ theo từng snapshot
curl -s localhost:18181/v1/namespaces/bronze/tables/cdc_events | python3 -c "
import sys,json
for s in json.load(sys.stdin)['metadata']['snapshots']:
    m=s['summary']; print(s['timestamp-ms'], 'added', m.get('added-records'), 'total', m.get('total-records'))"

# File Parquet và metadata trên MinIO (console: http://localhost:19001, ironman / ironman-secret)
docker run --rm --network ironman_default --entrypoint sh \
  minio/mc@sha256:a7fe349ef4bd8521fb8497f55c6042871b2ae640607cf99d9bede5e9bdf11727 \
  -c 'mc alias set l http://minio:9000 ironman ironman-secret >/dev/null; mc ls --recursive l/warehouse'
```

Bảng `bronze.cdc_events` chỉ xuất hiện sau checkpoint đầu tiên của Flink (10 đến 20 giây sau khi job lên).

## 5. Query để kiểm tra

Mỗi event CDC là **một dòng** của bảng `bronze.cdc_events` (nhật ký thay đổi, append-only, không phải bản sao của `orders`). Các cột chính: `source_table`, `op` (`r` snapshot, `c` insert, `u` update, `d` delete), `deleted`, `lsn`, `kafka_topic/partition/offset`, `row_json`, `before_json`, `after_json`, `ingest_ts`.

### 5.1. StarRocks + DBeaver

DBeaver: New Connection → **MySQL** → Host `localhost`, Port `19030`, User `root`, Password để trống. Nếu báo `Public Key Retrieval is not allowed`, đặt driver property `allowPublicKeyRetrieval=true`. (Mình chưa mở DBeaver để thử; đã kiểm chứng StarRocks nhận kết nối MySQL.)

Hoặc dùng client trong container (client `mysql` 9.x trên máy host không kết nối được vì đã bỏ plugin `mysql_native_password`):

```bash
docker exec -it ironman-starrocks mysql -h127.0.0.1 -P9030 -uroot
```

Luôn ghi đủ `ice.bronze.cdc_events` (catalog `ice`). Cây thư mục DBeaver không duyệt được external catalog.

```sql
SET query_timeout = 60;
REFRESH EXTERNAL TABLE ice.bronze.cdc_events;   -- StarRocks cache metadata Iceberg, refresh để thấy snapshot mới nhất

-- Số event theo bảng và loại thao tác
SELECT source_table, op, COUNT(*) AS n FROM ice.bronze.cdc_events GROUP BY source_table, op ORDER BY 1, 2;

-- Trạng thái hiện tại của orders: event mới nhất theo lsn của mỗi id, bỏ dòng đã xoá
SELECT id, status FROM (
  SELECT get_json_string(row_json, '$.id') AS id, get_json_string(row_json, '$.status') AS status, deleted,
         row_number() OVER (PARTITION BY get_json_string(row_json, '$.id') ORDER BY lsn DESC) AS rn
  FROM ice.bronze.cdc_events WHERE source_table = 'public.orders') t
WHERE rn = 1 AND NOT deleted ORDER BY id;

-- Lịch sử một đơn
SELECT kafka_partition, kafka_offset, op, get_json_string(after_json, '$.status') AS status, ingest_ts
FROM ice.bronze.cdc_events
WHERE source_table = 'public.orders' AND get_json_string(row_json, '$.id') = '1'
ORDER BY lsn DESC LIMIT 10;
```

### 5.2. DuckDB (không cần container)

```bash
python3 -m venv .venv && .venv/bin/pip install duckdb
.venv/bin/python
```

```python
import duckdb
c = duckdb.connect()
c.execute("INSTALL iceberg; LOAD iceberg; INSTALL httpfs; LOAD httpfs;")
c.execute("""CREATE SECRET s3 (TYPE S3, KEY_ID 'ironman', SECRET 'ironman-secret', ENDPOINT 'localhost:19000',
             URL_STYLE 'path', USE_SSL false, REGION 'us-east-1')""")
c.execute("ATTACH 'warehouse' AS ice (TYPE ICEBERG, ENDPOINT 'http://localhost:18181', AUTHORIZATION_TYPE 'NONE')")
c.sql("SELECT source_table, op, count(*) FROM ice.bronze.cdc_events GROUP BY ALL ORDER BY 1, 2").show()
```

DuckDB đọc snapshot mới nhất mỗi lần, không bị cache như StarRocks.

## 6. Kiểm tra end-to-end

Khi `pg-updater` đang chạy, Postgres luôn nhanh hơn Iceberg tối đa một chu kỳ checkpoint (10 giây), nên so sánh lúc đó sẽ lệch. Để đối chiếu chính xác:

```bash
docker stop ironman-pg-updater      # dừng nguồn thay đổi
sleep 30                            # đợi ít nhất 1 checkpoint
docker exec ironman-postgres psql -U ironman -d ironman -tAc "SELECT id, status FROM orders ORDER BY id"
```

Rồi chạy `REFRESH EXTERNAL TABLE` và câu "Trạng thái hiện tại của orders" ở mục 5.1 (hoặc bản DuckDB). Hai kết quả phải **giống hệt nhau**. Đã kiểm chứng: sau refresh, StarRocks và DuckDB đều khớp Postgres. Bật lại updater: `docker start ironman-pg-updater`.

Lưu ý: event `update` có `before_json = NULL`, và event `delete` chỉ mang cột khoá chính trong `before_json`, trừ khi bảng bật `ALTER TABLE <bảng> REPLICA IDENTITY FULL` ở Postgres.

## 7. Dừng và dọn

```bash
docker compose -f $F --profile flink down -v     # xoá hết container và dữ liệu (Postgres, Kafka, MinIO, Iceberg)
```

Muốn tạm dừng mà giữ dữ liệu, dùng `stop` rồi `start` (không có `-v`). **Cẩn thận với Flink:** job chạy ở application mode không có HA, nên khi JobManager khởi động lại mà không có savepoint, job bắt đầu mới và đọc lại **từ đầu topic**, làm bảng bronze có thêm các dòng trùng. Bronze vốn giao hàng at-least-once (trùng được xử lý ở silver). Muốn tiếp tục đúng chỗ thì tạo savepoint trước khi dừng: xem mục "Thử phục hồi lỗi" trong [`com/tm/flink/SETUP.md`](com/tm/flink/SETUP.md).

## 8. Xử lý sự cố

| Triệu chứng | Nguyên nhân thường gặp | Cách xử lý |
|---|---|---|
| `pull access denied ... com.tm.*` khi `up` | Chưa load image vào Docker (Go hoặc Flink) | Chạy lại mục 2 |
| DBeaver: `Communications link failure` / `Connection refused` ở 19030 | Stack chưa chạy (hoặc đã `down`), StarRocks chưa `healthy` | `docker compose ... ps`, đợi `healthy`, xem `docker logs ironman-starrocks` |
| Query báo không thấy bảng `ice.bronze.cdc_events` | Flink chưa qua checkpoint đầu tiên | Đợi 10 đến 20 giây, kiểm tra job `RUNNING` ở http://localhost:18081 |
| StarRocks trả dữ liệu cũ | Cache metadata Iceberg | `REFRESH EXTERNAL TABLE ice.bronze.cdc_events;` |
| Query StarRocks treo rất lâu (gặp 1 lần ở lần chạy đầu) | Chưa rõ, nghi BE nguội | `SET query_timeout=60;`, `KILL <id>` (xem `SHOW PROCESSLIST`) rồi chạy lại |
| Job Flink `RESTARTING` mãi | Xem `docker logs ironman-flink-jobmanager \| grep -i exception` | Lỗi trong job hoặc kết nối Kafka/Iceberg; JobManager và TaskManager phải dùng cùng image `com.tm.flink.cdc_flatten` |
| Sửa code job nhưng không có hiệu lực | Container vẫn chạy image cũ | `bazel run --config=linux-arm64 //com/tm/flink:cdc_flatten_docker` rồi `docker compose ... --profile flink up -d --force-recreate flink-jobmanager flink-taskmanager` |
| `debezium-register` Exit 1 | Task connector FAILED | `docker logs ironman-debezium`, `curl localhost:8084/connectors/ironman-pg/status` |
| Bảng bronze có dòng trùng | Job Flink đã khởi động lại không qua savepoint | Bình thường với at-least-once; dedup ở silver (theo `kafka_topic, kafka_partition, kafka_offset`) |

## 9. Cổng và tài khoản

| Dịch vụ | Địa chỉ | Tài khoản |
|---|---|---|
| Postgres | `localhost:5434` | `ironman` / `ironman`, db `ironman` |
| Kafka (từ máy host) | `localhost:39092` | |
| Debezium REST | http://localhost:8084 | |
| Flink UI | http://localhost:18081 | |
| Iceberg REST | http://localhost:18181 | |
| MinIO console | http://localhost:19001 | `ironman` / `ironman-secret` |
| StarRocks (MySQL) | `localhost:19030` | `root`, không mật khẩu |
| StarRocks FE HTTP | http://localhost:18030 | |
