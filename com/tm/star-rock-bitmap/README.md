# star-rock-bitmap: so sánh 2 cách xử lý tag/segment bằng RoaringBitmap

So sánh hiệu năng giữa việc tính segment ở service (bitmap lưu trong MongoDB) và tính ngay trong StarRocks (bitmap native).

## Bài toán

- Gold table trong StarRocks (SR) mô phỏng `aggregating_tag_not_mutex_most_recent` của core-service: mỗi dòng là `(attribute_id, actor_id, tag_id, latest_signal, last_persist_time)`, `latest_signal` là 1 (ADD) hoặc -1 (REMOVE). `actor_id` là `INT` (32-bit), nên dùng `org.roaringbitmap.RoaringBitmap` (32-bit). Khi build bitmap chỉ lấy dòng `latest_signal = 1`.
- Mỗi **tag** (attribute) có **10M–20M user**.
- Mỗi **segment** gồm **10 điều kiện (tag)** ghép với nhau bằng `AND` / `OR` / `NOT` (kiểu `a AND NOT b`).
- Cần hai thao tác đọc trên segment:
  - **Get user by segment**: lấy danh sách user của segment.
  - **Check contains**: kiểm tra 1 user có thuộc segment không.

## Hai pipeline

```
A) Mongo blob + compute ở service
   SR gold ──(1) build bitmap──► Mongo (GridFS blob: tag-N)
   Mongo ──(2) fetch 10 tag──► service: AND/OR/NOT ──► Mongo (blob: segment-S)

B) SR native bitmap + compute trong SR
   SR gold ──(1) INSERT ... bitmap_agg()──► tag_bitmap (BITMAP_UNION)
   tag_bitmap ──(2) bitmap_and/or/andnot ──► segment_bitmap (native)
```

| | A: Mongo + service | B: SR native |
|---|---|---|
| Tag bitmap | blob roaring trong Mongo | cột `BITMAP` trong `tag_bitmap` |
| Compute segment | Java service (`RoaringBitmap`) | SQL `bitmap_and/or/andnot` |
| Lưu segment | blob trong Mongo | `segment_bitmap` |
| Contains | tải blob rồi `Contains()` | `bitmap_contains(bm, uid)` |
| Get users | tải blob rồi iterate | `unnest(bitmap_to_array(bm))` |

## Hai chỗ cần đo

### 1. Bảng SR → bitmap (`etl`)

| Metric | Ý nghĩa |
|---|---|
| `A1` | SR gold → bitmap trong service. Có 2 chế độ `--export`: `agg` (SR gom bitmap, trả 1 blob base64) hoặc `rows` (kéo từng `actor_id` về rồi build) |
| `A2` | Serialize roaring (`RunOptimize` + `ToBytes`) |
| `A3` | Ghi blob vào Mongo |
| `B1` | `INSERT INTO tag_bitmap SELECT tag_id, bitmap_agg(actor_id) ... WHERE attribute_id = ? AND tag_id = ? AND latest_signal = 1 GROUP BY tag_id` chạy hoàn toàn trong SR |

Đo thêm kích thước blob trung bình mỗi tag.

### 2. Compute và lưu segment (`segment`)

| Metric | Ý nghĩa |
|---|---|
| `A4` | Fetch 10 tag blob từ Mongo (song song) và decode |
| `A5` | Tính AND/OR/NOT trong memory |
| `A6` / `A7` | Serialize và ghi segment vào Mongo |
| `A total` | A4 + A5 + A6 + A7 |
| `B total` | 1 câu `INSERT INTO segment_bitmap SELECT ...` (compute và lưu) |

Mỗi segment được đối chiếu `cardinality` giữa A và B, để chắc hai bên cùng ra một kết quả.

### 3. Đọc segment (`read`)

Đo `contains` và `get 1000 user` cho cả A và B, lặp `--reads` lần trên các segment và user ngẫu nhiên.

## Cấu trúc bảng gold: `aggregating_tag_not_mutex_most_recent`

Mô phỏng bảng cùng tên của core-service. Cột của bảng thật được suy ra từ SQL trong `LakehouseAttributeDataDAO`, không có DDL trong repo, nên kiểu dữ liệu và khóa bên dưới là của benchmark, không phải bản sao của bảng thật.

| Cột | Native SR | Iceberg | Ý nghĩa |
|---|---|---|---|
| `attribute_id` | `INT NOT NULL` | `INT` | Attribute chứa tag |
| `actor_id` | `INT NOT NULL` | `INT` | userId (32-bit) |
| `tag_id` | `INT NOT NULL` | `INT` | Tag |
| `latest_signal` | `SMALLINT NOT NULL` | `INT` | 1 = ADD (đang gắn tag), -1 = REMOVE |
| `last_persist_time` | `DATETIME NOT NULL` | `DATETIME` | Thời điểm ghi gần nhất |

- **Khóa (native):** `DUPLICATE KEY(attribute_id, actor_id, tag_id)`, `DISTRIBUTED BY HASH(actor_id) BUCKETS 32`, `replication_num = 1`. Dữ liệu sinh ra không trùng `(attribute_id, actor_id, tag_id)`, nên mỗi tổ hợp có đúng 1 dòng như ngữ nghĩa "most recent".
- **Iceberg:** không khai báo khóa hay phân phối, không partition.
- **Kích thước:** mỗi tag có khoảng 10M–20M dòng signal 1, cộng thêm `--removed-pct` dòng signal -1.

## Câu lệnh tạo bảng

Đây là đúng các câu `Sr.load` chạy (`src/Sr.java`). Lệnh `load` tự tạo hết, không cần chạy tay.

```sql
CREATE DATABASE IF NOT EXISTS bm_bench;
```

Gold, native SR (mặc định):

```sql
CREATE TABLE IF NOT EXISTS bm_bench.aggregating_tag_not_mutex_most_recent (
    attribute_id      INT      NOT NULL,
    actor_id          INT      NOT NULL,
    tag_id            INT      NOT NULL,
    latest_signal     SMALLINT NOT NULL,
    last_persist_time DATETIME NOT NULL
)
DUPLICATE KEY(attribute_id, actor_id, tag_id)
DISTRIBUTED BY HASH(actor_id) BUCKETS 32
PROPERTIES("replication_num" = "1");
```

Gold, Iceberg (khi có `--gold-catalog <catalog>`; `load` DROP bảng cũ rồi tạo lại):

```sql
CREATE DATABASE IF NOT EXISTS <catalog>.bm_bench;
DROP TABLE IF EXISTS <catalog>.bm_bench.aggregating_tag_not_mutex_most_recent;
CREATE TABLE IF NOT EXISTS <catalog>.bm_bench.aggregating_tag_not_mutex_most_recent (
    attribute_id      INT,
    actor_id          INT,
    tag_id            INT,
    latest_signal     INT,
    last_persist_time DATETIME
);
```

Bitmap của tag (pipeline B), luôn là bảng native:

```sql
CREATE TABLE IF NOT EXISTS bm_bench.tag_bitmap (
    tag_id INT NOT NULL,
    bm     BITMAP BITMAP_UNION NOT NULL
)
AGGREGATE KEY(tag_id)
DISTRIBUTED BY HASH(tag_id) BUCKETS 8
PROPERTIES("replication_num" = "1");
```

Bitmap của segment (pipeline B), luôn là bảng native:

```sql
CREATE TABLE IF NOT EXISTS bm_bench.segment_bitmap (
    segment_id INT NOT NULL,
    bm         BITMAP BITMAP_UNION NOT NULL
)
AGGREGATE KEY(segment_id)
DISTRIBUTED BY HASH(segment_id) BUCKETS 8
PROPERTIES("replication_num" = "1");
```

Pipeline A không có bảng SR riêng. Bitmap của tag và segment nằm trong GridFS của MongoDB (collection `fs.files` / `fs.chunks` của database `bm_bench`), tên file là `tag-<id>` và `segment-<id>`.

## Query chuyển gold thành bitmap

`<gold>` là `bm_bench.aggregating_tag_not_mutex_most_recent` (native) hoặc `<catalog>.bm_bench.aggregating_tag_not_mutex_most_recent` (Iceberg, khi có `--gold-catalog`). Điều kiện lọc chung của mọi query dưới đây: `attribute_id = ? AND tag_id = ? AND latest_signal = 1`.

### Pipeline A: Mongo (bitmap build ở service, `Sr.fetchTag`)

Chế độ `--export agg` (mặc định): SR gom bitmap, chỉ trả về 1 blob.

```sql
SELECT bitmap_to_base64(bitmap_agg(actor_id))
  FROM <gold>
 WHERE attribute_id = ? AND tag_id = ? AND latest_signal = 1
```

Service giải mã base64 theo định dạng bitmap của SR (`BitmapCodec.decodeStarRocks`), `runOptimize()`, serialize roaring portable rồi ghi vào GridFS với tên `tag-<tag_id>`, chunk 8MB.

Chế độ `--export rows`: kéo từng user về, service tự build.

```sql
SELECT actor_id
  FROM <gold>
 WHERE attribute_id = ? AND tag_id = ? AND latest_signal = 1
```

Đọc streaming (`setFetchSize(Integer.MIN_VALUE)`), gom 65536 id mỗi lượt vào `RoaringBitmap.addN`, sau đó serialize và ghi GridFS như trên.

### Pipeline B: bitmap native của SR (`Bench.etl`)

```sql
DELETE FROM bm_bench.tag_bitmap WHERE tag_id = ?;   -- không tính vào thời gian đo

INSERT INTO bm_bench.tag_bitmap
SELECT tag_id, bitmap_agg(actor_id)
  FROM <gold>
 WHERE attribute_id = ? AND tag_id = ? AND latest_signal = 1
 GROUP BY tag_id
```

`tag_bitmap` là bảng `AGGREGATE KEY(tag_id)` với cột `bm BITMAP BITMAP_UNION`, nên SR tự gộp các bitmap cùng `tag_id`. Cả quá trình chạy trong SR, không có dữ liệu đi qua service. Nếu gold ở Iceberg thì đây là lúc SR đọc file Parquet.

`tag_bitmap` và `segment_bitmap` chỉ khóa theo `tag_id` / `segment_id`, vì benchmark sinh `tag_id` duy nhất trên toàn bộ attribute.

### Query tính và đọc segment (để so sánh)

Pipeline A tải 10 blob `tag-<id>` từ GridFS song song, tính bằng `RoaringBitmap.and/or/andNot` trong memory, ghi lại thành `segment-<id>`. Pipeline B chạy một câu SQL, ví dụ:

```sql
INSERT INTO bm_bench.segment_bitmap
SELECT 3, bitmap_andnot(bitmap_and(t1.bm, t4.bm), t7.bm)
  FROM (SELECT bitmap_union(bm) AS bm FROM bm_bench.tag_bitmap WHERE tag_id = 1) t1
  CROSS JOIN (SELECT bitmap_union(bm) AS bm FROM bm_bench.tag_bitmap WHERE tag_id = 4) t4
  CROSS JOIN (SELECT bitmap_union(bm) AS bm FROM bm_bench.tag_bitmap WHERE tag_id = 7) t7
```

(ví dụ rút gọn 3 tag, thực tế là 10 tag.) Đọc segment ở B: `bitmap_contains(bm, ?)` và `unnest(bitmap_to_array(bm)) ... LIMIT 1000`; ở A: tải blob rồi `contains()` hoặc duyệt 1000 phần tử đầu.

## Dữ liệu test

Sinh **ngay trong SR**, không đi qua mạng:

- Universe mặc định là 50M user (`--universe`), `actor_id` từ `1..50M`.
- Mỗi tag có mật độ 20–40% universe, tức 10M–20M user (`--min-pct`, `--max-pct`).
- Với `h = abs(murmur_hash3_32(u, t)) % 10000`: `h < pct*100` thì có dòng signal 1 (thành viên tag); `pct*100 <= h < (pct+removed)*100` thì có dòng signal -1 (đã bị REMOVE, phải bị loại). Kết quả xác định theo `t`, chạy lại ra cùng dữ liệu.
- `--removed-pct` (mặc định 5) là tỉ lệ dòng REMOVE so với universe. `--tags-per-attribute` (mặc định 5) chia tag 1..N vào attribute 1.. theo thứ tự. `last_persist_time` sinh ngẫu nhiên trong ngày 2026-01-01.
- Mặc định gold là bảng native của SR (`bm_bench.aggregating_tag_not_mutex_most_recent`). Core-service đọc gold từ Iceberg qua external catalog, nên để đo sát thực tế hãy truyền `--gold-catalog <tên catalog>` (ví dụ `iceberg_catalog_hms`): `load` sẽ tạo database `bm_bench` và bảng gold trong catalog đó (DROP rồi CREATE lại), sinh data bằng `INSERT INTO ... SELECT` từ SR, và mọi bước đọc gold đều đi qua catalog. `tag_bitmap` và `segment_bitmap` vẫn là bảng native, vì Iceberg không có kiểu BITMAP.
- Cần catalog đã tạo sẵn và SR có quyền ghi (CREATE TABLE / INSERT vào Iceberg cần SR 3.1 trở lên). Chế độ này chưa được kiểm chứng.
- Mặc định 30 tag, tổng khoảng 450M dòng gold. Có thể giảm bằng `--tags` hoặc `--universe` khi cần chạy thử nhanh.
- Segment sinh ngẫu nhiên (`--seed`): chọn 10 tag khác nhau, ghép dần bằng cây biểu thức với tỉ lệ AND 50%, OR 30%, AND NOT 20%.

## Quyết định thiết kế cần lưu ý

- **Mongo dùng GridFS, chunk 8MB** (`MongoStore.CHUNK_SIZE`). Bitmap 20M user trên universe 50M nặng vài MB đến chục MB, có thể chạm giới hạn 16MB của một document. Blob lớn hơn 8MB được tách thành nhiều chunk, blob nhỏ hơn nằm trong 1 chunk.
- **`NOT` được hiểu là `a AND NOT b`** (`bitmap_andnot`). Một `NOT` đứng riêng cần thêm bitmap toàn bộ user (universe), hiện chưa dùng.
- **Chỉ hỗ trợ 32-bit**, đúng giả định userId là `int`.
- **Giải mã bitmap SR ở pipeline A (chế độ `agg`):** `bitmap_to_base64` dùng định dạng BitmapValue của SR (byte đầu là type: EMPTY, SINGLE32, BITMAP32 portable roaring, SINGLE64, SET với giá trị 8 byte; BITMAP64 báo lỗi). `BitmapCodec.decodeStarRocks` làm theo `StarrocksBitmapCodec` của core-service (lib `lib_cdp-segment-bitmap-starrocks`, đã kiểm chứng trên SR 3.5.19), nhưng bản của benchmark chưa chạy với SR thật. Bước đối chiếu cardinality sẽ báo ngay nếu decode sai.
- **Giới hạn kích thước gói tin SR:** blob base64 từ SR cần nhỏ hơn `max_allowed_packet` (mặc định 32MB). Với universe 50M thì vẫn dưới ngưỡng này.
- **Cache:** mặc định mỗi lần đọc đều chạy lạnh, tức A luôn tải blob từ Mongo. Một service thật có thể cache bitmap nóng trong memory, và nên đo thêm trường hợp đó nếu cần.

## Cách chạy

Cần SR (MySQL port 9030) và MongoDB chạy sẵn (hoặc dùng profile `bitmap` bên dưới). Mọi lệnh chạy từ thư mục gốc repo:

```bash
bazel run //com/tm/star-rock-bitmap:bench -- load      # tạo schema + sinh gold
bazel run //com/tm/star-rock-bitmap:bench -- etl       # đo bước 1: SR -> bitmap
bazel run //com/tm/star-rock-bitmap:bench -- segment   # đo bước 2: compute + lưu segment
bazel run //com/tm/star-rock-bitmap:bench -- read      # đo contains / get users
bazel run //com/tm/star-rock-bitmap:bench -- all
bazel test //com/tm/star-rock-bitmap:segment_expr_test # test logic, không cần SR/Mongo
```

Flags chính: `--gold-catalog`, `--tags-per-attribute`, `--removed-pct`, `--sr` (JDBC URL), `--sr-user`, `--sr-password`, `--mongo`, `--mongo-db`, `--tags`, `--universe`, `--min-pct`, `--max-pct`, `--segments`, `--leaves`, `--export agg|rows`, `--reads`, `--seed`.

Kết quả in dạng bảng `min / p50 / p95 / max` cho từng metric.

## Cấu trúc code (`src/`)

| File | Vai trò |
|---|---|
| `Main.java` | Entry point, chọn lệnh |
| `Config.java` | Parse flag |
| `Sr.java` | DDL, sinh gold, kéo tag từ SR (`agg` / `rows`) |
| `MongoStore.java` | Blob bitmap trong GridFS |
| `BitmapCodec.java` | Serialize roaring, giải mã bitmap SR |
| `SegmentExpr.java` | Cây AND/OR/NOT: sinh ngẫu nhiên, eval trong memory, render SQL |
| `Bench.java` | `etl`, `segment`, `read` |
| `Stats.java` | Đo thời gian và in bảng |

## Chạy với docker compose

```bash
docker compose -f com/tm/docker/ironman/docker-compose.yml --profile bitmap up -d --no-deps \
  starrocks-bitmap mongo-bitmap mongo-exporter-bitmap prometheus-bitmap grafana-bitmap
bazel build //com/tm/star-rock-bitmap:bench_deploy.jar
cp bazel-bin/com/tm/star-rock-bitmap/bench_deploy.jar com/tm/docker/ironman/bitmap/bench.jar
python3 com/tm/docker/ironman/bitmap/docker_stats_exporter.py &   # CPU, RAM, network theo container
com/tm/star-rock-bitmap/run_all.sh /tmp/run1                       # load, Mongo rows, Mongo agg, StarRocks
```

Giới hạn tài nguyên (đặt trong compose): StarRocks 6 CPU và 8GB, MongoDB 3 CPU và 6GB, service benchmark 2 CPU và 3GB (service chạy trong container `bench-bitmap`, profile `bench`). Grafana http://localhost:23000 (admin/admin, dashboard `bitmap-bench`), Prometheus http://localhost:29090. Muốn chạy lại sạch thì xoá ba volume `ironman_starrocks-bitmap-data`, `ironman_mongo-bitmap-data`, `ironman_prometheus-bitmap-data` rồi `up` lại.

Mỗi lúc chỉ xử lý một tag (bước tag) hoặc một segment (bước segment), và tạo xong cả 30 tag mới sang segment. Chỗ song song duy nhất là bước A4: tải 10 blob tag của cùng một segment từ Mongo bằng 10 luồng.

`--pipeline a|b|ab` chọn pipeline (mặc định `ab`, chạy xen kẽ), `run` là etl + segment + read không load lại gold. Benchmark mở `/metrics` ở cổng 9464 (`BENCH_METRICS_PORT`) để Prometheus thu avg, p50, p90, p99 của từng bước và size bitmap.

## Trạng thái hiện tại

- Đã chạy với StarRocks 3.5.8 và MongoDB 7 thật: SQL và bước giải mã bitmap SR hoạt động, cardinality của 600/600 segment khớp giữa ba pipeline, không có OOM.
- Kết quả lần chạy ngày 17/10/2026 (30 tag, universe 50M, 480M dòng gold, 600 segment, 4000 lần đọc; mỗi tag trung bình 13,5M user, mỗi segment trung bình 3,75MB), đơn vị ms. Giới hạn: StarRocks 6 CPU 8GB, Mongo 3 CPU 6GB, service 2 CPU 3GB:

| | Mongo rows | Mongo agg | StarRocks |
|---|---|---|---|
| Tag: gold → sẵn sàng (avg / p50 / p90 / p99) | 2780 / 2790 / 3400 / 3420 | 333 / 290 / 379 / 940 | 400 / 366 / 478 / 768 |
| Segment: avg / p50 / p90 / p99 | 108 / 104 / 149 / 208 | 94,3 / 91,2 / 130 / 164 | 115 / 103 / 137 / 316 |
| Contains: avg / p50 / p90 / p99 | 14,7 / 11,9 / 34,6 / 56,5 | 10,7 / 9,3 / 23,6 / 38,0 | 10,5 / 8,3 / 16,5 / 26,9 |
| Lấy 1000 user: avg / p50 / p90 / p99 | 14,1 / 11,6 / 34,0 / 56,2 | 9,9 / 9,2 / 22,6 / 37,3 | 9,1 / 8,4 / 11,2 / 18,0 |
| Size mỗi tag / segment (MB) | 6,26 / 3,75 | giống | giống |
| Tổng thời gian chạy | 264s | 151s | 227s |

  Tag: Mongo agg và StarRocks nhanh hơn nhiều so với Mongo rows (phải kéo từng user về service). Tạo segment: ba pipeline gần ngang nhau, khoảng 100ms. Đọc: StarRocks nhanh nhất, rõ nhất ở p99.
- StarRocks 3 CPU và 6GB so với 6 CPU và 8GB (p50): tag SR 690ms xuống 366ms, tag Mongo agg 492ms xuống 290ms, trong khi segment SR vẫn khoảng 103ms và đọc không đổi. Với 3 CPU, StarRocks chạm trần CPU 43% thời gian ở bước tag; với 6 CPU không lúc nào chạm trần (đỉnh 3,98 core). Bước segment không phụ thuộc CPU, mỗi segment là một câu SQL có chi phí cố định (lập kế hoạch, 10 subquery đọc `tag_bitmap`, commit `INSERT`), và đây là suy luận, chưa đo tách riêng. Mongo rows không đổi vì nghẽn ở service (một luồng đọc và build bitmap).
- Tài nguyên đỉnh (6 CPU và 8GB), service / Mongo / StarRocks: Mongo rows CPU 2,11 / 0,82 / 5,70 core, RAM 1,3 / 2,4 / 3,2GB; Mongo agg CPU 2,04 / 0,76 / 4,22, RAM 1,4 / 2,5 / 3,7GB; pipeline StarRocks CPU 0,95 / 0,46 / 3,98, RAM 1,4 / 2,5 / 6,0GB. Mongo gửi khoảng 67 đến 68GB về service trong hai lần chạy Mongo, còn pipeline StarRocks gần như không có network giữa các container.
- Compute của SR là cả câu SQL, của Mongo chỉ là bước AND/OR/NOT trong service. Size SR là ước lượng từ `bitmap_to_base64`. Mỗi pipeline chỉ chạy một lần, nên chênh lệch nhỏ giữa các lần (ví dụ Mongo agg đọc nhanh hơn một chút ở vòng này) có thể là nhiễu giữa các lần chạy.
- Đã thêm 3 dependency vào `MODULE.bazel` và pin lại `maven_install.json`: `RoaringBitmap:1.3.0`, `mongodb-driver-sync:5.2.1`, `mysql-connector-j:8.4.0`.
