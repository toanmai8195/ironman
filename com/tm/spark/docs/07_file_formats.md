# Step 07 — File format, partition, pruning

- **File:** `jobs/07_file_formats.py` · **Chạy:** job step 7 (cần step 1; ghi `/data/tmp/fmt/*`, vài trăm MB; tạo bảng `o_bucketed`, `c_bucketed` trong `data/warehouse`)
- **Mục đích:** cách lưu dữ liệu quyết định phần lớn tốc độ đọc.
- **Docs:** https://spark.apache.org/docs/latest/sql-data-sources.html · https://spark.apache.org/docs/latest/sql-data-sources-parquet.html

## Khái niệm mới

- **Định dạng hàng vs cột:** CSV/JSON lưu từng dòng dạng text, đọc một cột vẫn phải parse cả dòng. Parquet/ORC lưu theo cột, nén tốt, chỉ đọc cột cần (**column pruning**).
- **Row group và thống kê:** Parquet chia file thành các row group, mỗi cái lưu min/max từng cột. Với `WHERE x > 10`, Spark bỏ qua row group có max < 10 (**predicate pushdown**, hiện trong plan là `PushedFilters`).
- **Compression codec:** snappy (mặc định, nhanh), gzip/zstd (nhỏ hơn, tốn CPU hơn).
- **Hai nghĩa của "partition" (dễ nhầm):** *Spark partition* là mảnh dữ liệu trong bộ nhớ khi chạy (step 00). *Hive-style partition* là cấu trúc thư mục trên đĩa, `partitionBy("col")` tạo `col=value/`.
- **Partition pruning:** query có lọc theo cột partition chỉ đọc thư mục khớp, hiện trong plan là `PartitionFilters`.
- **Small files problem:** quá nhiều file nhỏ làm chậm việc liệt kê và mở file, tạo quá nhiều task. Nguyên nhân thường gặp: `partitionBy` cột nhiều giá trị mà không gom dữ liệu cùng giá trị về một task. Cách chữa: `repartition(col)` hoặc `coalesce` trước khi ghi.
- **`mergeSchema`:** khi các file có schema khác nhau (thêm cột), hợp nhất thành schema chung thay vì lấy của file đầu.
- **Bucketing:** `bucketBy(n, col)` chia dữ liệu thành n nhóm cố định theo hash của cột ngay khi lưu; hai bảng cùng bucket theo khoá join có thể join mà không shuffle. Chỉ dùng được với `saveAsTable`.
- **`saveAsTable` và warehouse:** ghi thành bảng có tên trong catalog, dữ liệu nằm ở `spark.sql.warehouse.dir` (đặt là `/data/warehouse`).

| # | Mục trong file | Làm gì | Quan sát |
|---|---|---|---|
| 1 | Ghi `orders` ra CSV/JSON/ORC/Parquet, đo kích thước và thời gian đọc 1 cột | So bốn định dạng | CSV/JSON dạng text, parse cả dòng; Parquet/ORC dạng cột, nén, đọc đúng cột cần |
| 2 | `compression` = snappy / gzip / zstd | So mức nén | snappy nhanh, gzip/zstd nhỏ hơn |
| 3 | `partitionBy("order_month")` | Mỗi tháng một thư mục `order_month=2025-03/` | Đếm số thư mục và file |
| 4 | `filter(order_month=... & status=...)` rồi `explain()` | Partition pruning + predicate pushdown + column pruning | `PartitionFilters`, `PushedFilters`, `ReadSchema` chỉ có cột cần |
| 5 | `partitionBy("order_date")` không / có `repartition("order_date")` | **Small files** | Không repartition: mỗi task ghi 1 file mỗi ngày, hàng nghìn file; có repartition: ~730 file |
| 6 | Đọc thư mục partition; `mergeSchema` | Suy ra cột partition; schema khác nhau giữa các file | |
| 7 | `bucketBy(8, "customer_id").sortBy(...).saveAsTable` | Join hai bảng cùng bucket không cần shuffle | `explain()` không có `Exchange` ở hai nhánh so với join thường |

**Quy tắc:** file 128MB-1GB; partition theo cột cardinality thấp (ngày, tháng, quốc gia), không theo `user_id`; gom (`repartition`/`coalesce`) trước khi ghi.

**Bài tập:** thử `partitionBy("order_month", "status")` và đếm file; đọc `by_day_bad` và `by_day_good` đo thời gian khác nhau.

## Definition of Done

Xong step khi **tất cả** các ô dưới đây đúng; chưa đúng thì chưa sang step sau.

- [ ] job step 7 chạy hết, không lỗi.
- [ ] Mục 1: bảng so sánh 4 định dạng cho thấy Parquet/ORC nhỏ hơn và đọc 1 cột nhanh hơn CSV/JSON.
- [ ] Mục 4: chỉ đúng `PartitionFilters`, `PushedFilters`, `ReadSchema` trong plan.
- [ ] Mục 5: số file `by_day_bad` lớn hơn nhiều `by_day_good`, và bạn giải thích nguyên nhân.
- [ ] Mục 7: plan bucketed không có `Exchange`, plan thường có.
- [ ] Phân biệt được hai nghĩa của "partition" (Spark partition và thư mục Hive-style).
