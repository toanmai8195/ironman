# Học PySpark qua bài toán "Ironshop" (đơn hàng + clickstream)

Cùng bối cảnh cửa hàng online với `com/tm/pg`, nhưng lần này là **xử lý dữ liệu lớn**: 1 triệu đơn, ~2,5 triệu dòng item, 1 triệu event clickstream bẩn. Mỗi step thêm một nhóm khái niệm Spark lên cùng bộ dữ liệu, kết thúc bằng pipeline bronze → silver → gold.

Tham khảo: https://spark.apache.org/docs/latest/ · PySpark API: https://spark.apache.org/docs/latest/api/python/

## Chạy

Cần Docker. Spark chạy local mode trong container `apache/spark:3.5.3-python3` (không cần cài Java/Python).

```bash
cd com/tm/spark
./run.sh step 1        # sinh dữ liệu vào data/ (làm 1 lần)
./run.sh step 2        # làm sạch events → data/events (cần cho step 3 trở đi)
./run.sh step 3        # chạy từng step
./run.sh all           # chạy 00 → 10 tuần tự
./run.sh shell         # pyspark REPL;  ./run.sh sql  → spark-sql
CORES=8 MEM=6g ./run.sh step 8
HOLD=300 ./run.sh step 8    # giữ job 300s để xem Spark UI: http://localhost:4040
./run.sh clean         # xoá data/
```

Cách học: đọc doc của step, mở file `jobs/NN_*.py`, chạy rồi đọc output cạnh code. Mỗi mục trong file là `section("...")` nên output có tiêu đề tương ứng. Sửa tham số rồi chạy lại để thấy khác biệt (đổi `shuffle.partitions`, tắt AQE, bỏ `broadcast`...).

## Dữ liệu (sinh ở step 01/02)

| Dataset | Dòng | Định dạng | Ghi chú để học |
|---|---|---|---|
| customers | 50.000 | parquet | `city` có NULL |
| products | 2.500 | parquet | bảng nhỏ → broadcast |
| orders | 1.000.000 | parquet | 5% đơn thuộc khách id=1 (**hot key / skew**); khách > 45000 chưa mua |
| order_items | ~2.500.000 | parquet | `line_total` = qty × unit_price |
| events_raw | ~1.010.000 | JSON | **bẩn**: ~1% trùng `event_id`, ~3% thiếu `user_id`, `ts` là chuỗi |
| events | ~960.000 | parquet | bản sạch do step 02 ghi |

## Lộ trình

| Step | File | Chủ đề | Doc |
|---|---|---|---|
| 00 | (chỉ đọc doc, không có code) | SparkSession, DataFrame, lazy evaluation, shuffle, plan | [docs/00_basics.md](docs/00_basics.md) |
| 01 | `jobs/01_generate_data.py` | Sinh dữ liệu bằng Spark, ghi parquet/JSON | [docs/01_generate_data.md](docs/01_generate_data.md) |
| 02 | `jobs/02_transformations.py` | select/filter/withColumn, NULL, chuỗi, ngày, array, JSON lỗi, dedupe | [docs/02_transformations.md](docs/02_transformations.md) |
| 03 | `jobs/03_aggregations.py` | groupBy, distinct xấp xỉ, pivot, rollup, funnel | [docs/03_aggregations.md](docs/03_aggregations.md) |
| 04 | `jobs/04_joins.py` | Mọi loại join, broadcast vs sort-merge, skew | [docs/04_joins.md](docs/04_joins.md) |
| 05 | `jobs/05_window.py` | Window function, sessionization | [docs/05_window.md](docs/05_window.md) |
| 06 | `jobs/06_sql_udf.py` | Spark SQL, UDF vs built-in, higher-order function | [docs/06_sql_udf.md](docs/06_sql_udf.md) |
| 07 | `jobs/07_file_formats.py` | Định dạng, nén, partitionBy, pruning, small files, bucketing | [docs/07_file_formats.md](docs/07_file_formats.md) |
| 08 | `jobs/08_performance.py` | Shuffle partitions, AQE, cache, repartition, Spark UI | [docs/08_performance.md](docs/08_performance.md) |
| 09 | `jobs/09_streaming.py` | Structured Streaming, watermark, checkpoint | [docs/09_streaming.md](docs/09_streaming.md) |
| 10 | `jobs/10_pipeline.py` | Pipeline bronze/silver/gold, quality gate, incremental | [docs/10_pipeline.md](docs/10_pipeline.md) |
| 11 | `jobs/11_iceberg.py` | Iceberg: MERGE, time travel, schema/partition evolution, đọc từ StarRocks (dùng lại Parquet, không seed lại) | [docs/11_iceberg.md](docs/11_iceberg.md) |

`jobs/common.py` là helper chung (SparkSession, `timed()` đo bằng sink `noop`, đếm file/dung lượng, `hold()`).

## Lưu ý

- Local mode chỉ có 1 JVM nên **thời gian là để so sánh tương đối** giữa hai cách làm, không phải benchmark cluster. Hiệu ứng như shuffle, skew, small files vẫn tái hiện đúng.
- Mặc định 4 core / 3GB; máy yếu thì giảm dữ liệu (`N_ORD`, `N_EVT` đầu `01_generate_data.py`).
- Cùng đối tượng học với `com/tm/flink` (stream) và `com/tm/star-rock-bitmap`; Spark ở đây thiên về batch + SQL.

## Checklist

Tick khi trả lời được các câu tự kiểm tra của step đó mà không cần nhìn doc.

- [ ] **00 Nền tảng**: Vì sao `filter` không chạy ngay mà `count` mới chạy? Narrow và wide khác nhau thế nào, shuffle là gì và thấy nó ở đâu trong plan? Job, stage, task liên hệ nhau ra sao?
- [ ] **01 Sinh dữ liệu**: Column expression là giá trị hay là mô tả phép tính? Vì sao số file đầu ra bằng số partition lúc ghi? Parquet khác JSON lines ở điểm nào?
- [ ] **02 Biến đổi**: Vì sao `col != 'x'` làm mất dòng NULL và sửa thế nào? Ba mode đọc JSON lỗi khác nhau ra sao? `dropDuplicates` có giữ bản mới nhất không?
- [ ] **03 Aggregation**: Vì sao aggregate có hai pha và lợi gì? Khi nào dùng `approx_count_distinct`? `pivot` nên truyền sẵn giá trị vì sao? Dòng NULL trong `rollup` nghĩa là gì?
- [ ] **04 Join**: Chọn broadcast hay sort-merge dựa vào gì? Nhận ra skew bằng cách nào và có ba cách xử lý nào (salting, AQE, tách khoá nóng)? `left_semi` và `left_anti` khác `inner`/`left` thế nào?
- [ ] **05 Window**: `rows` khác `range` ra sao? Window không có `partitionBy` nguy hiểm vì sao? Viết được sessionization bằng `lag` + cờ + `sum`?
- [ ] **06 SQL và UDF**: Vì sao SQL và DataFrame API cùng hiệu năng? Vì sao UDF Python chậm và thay bằng gì (built-in, higher-order function)?
- [ ] **07 File format**: Hai nghĩa của "partition" là gì? Chỉ ra `PartitionFilters`, `PushedFilters`, `ReadSchema` trong plan. Small files sinh ra thế nào và chữa ra sao? Bucketing giúp gì cho join?
- [ ] **08 Performance**: Chọn `shuffle.partitions` theo nguyên tắc nào? AQE tự làm những gì? Khi nào cache đáng, `repartition` khác `coalesce` ra sao? Đọc Spark UI để tìm task chậm và spill.
- [ ] **09 Streaming**: Output mode nào dùng khi nào? Watermark làm gì với state? Checkpoint lưu gì và vì sao không đổi logic aggregation giữa các lần chạy? Vì sao `foreachBatch` phải idempotent?
- [ ] **10 Pipeline**: Bronze, silver, gold mỗi lớp giữ gì? `partitionOverwriteMode=dynamic` khác `overwrite` mặc định ở đâu? Quality gate chặn điều gì?
- [ ] **11 Iceberg**: Iceberg thêm gì so với Parquet thuần? Snapshot và commit nguyên tử là gì? Hidden partitioning và partition evolution giải quyết vấn đề nào? Vì sao phải compaction và `expire_snapshots`?

## Definition of Done

Mỗi doc có code ở `docs/` (từ step 01) có mục **Definition of Done** ở cuối; step 00 chỉ đọc doc nên không có. Mục này gồm: các điều kiện kiểm chứng được (chạy ra kết quả gì, giải thích được gì, tự làm được gì). Chỉ sang step sau khi tất cả ô của step hiện tại đúng, rồi mới tick step đó trong Checklist ở trên.
