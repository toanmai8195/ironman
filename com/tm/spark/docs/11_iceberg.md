# Step 11 — Iceberg với Spark

- **File:** `jobs/11_iceberg.py` (sẽ sinh khi học tới step này) · **Cần:** step 01–02 đã chạy (dùng lại Parquet, **không seed lại**) và stack MinIO + Iceberg REST + StarRocks của compose chung (`--profile flink`, xem `com/tm/docker/ironman/docker-compose.yml`)
- **Mục đích:** nâng Parquet thuần lên bảng có transaction, sửa/xoá dòng, time travel, đổi schema; rồi đọc cùng bảng từ StarRocks.
- **Docs:** https://iceberg.apache.org/docs/latest/spark-getting-started/ · https://iceberg.apache.org/docs/latest/spark-writes/ · https://iceberg.apache.org/spec/

## Khái niệm mới

- **Table format:** lớp metadata quản lý một tập file dữ liệu thành "bảng". Iceberg không thay Parquet; file dữ liệu vẫn là Parquet, Iceberg thêm metadata ghi lại file nào thuộc bảng ở thời điểm nào.
- **Catalog:** nơi lưu con trỏ tới metadata hiện tại của từng bảng. Ở đây dùng **REST catalog** (`iceberg-rest`) để Spark, Flink, StarRocks cùng thấy một bảng. Spark khai báo catalog bằng config `spark.sql.catalog.ice=org.apache.iceberg.spark.SparkCatalog` và `...type=rest`.
- **Snapshot / Manifest:** mỗi lần ghi tạo một *snapshot* (ảnh chụp trạng thái bảng); snapshot trỏ tới các *manifest* liệt kê file dữ liệu kèm thống kê. Commit là đổi con trỏ của catalog sang metadata mới nên **nguyên tử**: reader thấy snapshot cũ hoặc mới, không bao giờ thấy nửa vời.
- **Time travel:** đọc bảng tại snapshot hoặc thời điểm cũ (`VERSION AS OF`, `TIMESTAMP AS OF`), và `rollback` về snapshot cũ.
- **Row-level `MERGE INTO` / `UPDATE` / `DELETE`:** sửa dòng mà không tự ghi đè partition. Iceberg viết lại file bị ảnh hưởng (*copy-on-write*) hoặc ghi file xoá riêng (*merge-on-read*).
- **Schema evolution:** thêm, bỏ, đổi tên cột an toàn vì cột được định danh bằng id, không bằng tên hay vị trí.
- **Hidden partitioning:** khai báo partition bằng biến đổi (`days(created_at)`, `bucket(16, customer_id)`); người dùng chỉ lọc theo cột gốc, Iceberg tự prune. Đổi cách partition không phải viết lại dữ liệu cũ (**partition evolution**).
- **Bảo trì:** `rewrite_data_files` (compaction file nhỏ), `expire_snapshots` (xoá snapshot cũ để giải phóng file), `remove_orphan_files`. Mỗi lần ghi để lại file và snapshot nên phải dọn định kỳ.
- **Cấu hình Spark:** cần jar `iceberg-spark-runtime` khớp bản Spark/Scala, thêm qua `--packages` hoặc `--jars`, và extension `IcebergSparkSessionExtensions` để dùng `MERGE`, `CALL`.

## Các mục sẽ có trong file

| # | Mục | Làm gì | Quan sát |
|---|---|---|---|
| 1 | Cấu hình catalog `ice` (REST + S3 MinIO) | Spark nói chuyện với Iceberg REST | `SHOW NAMESPACES IN ice` chạy được |
| 2 | Nạp `orders`, `order_items`, `events` từ Parquet bằng `writeTo("ice.shop.orders").partitionedBy(days("created_at")).create()` | Chuyển Parquet thành bảng Iceberg | Dữ liệu nằm trong MinIO bucket `warehouse` |
| 3 | Xem bảng metadata: `ice.shop.orders.snapshots`, `.files`, `.manifests`, `.history` | Hiểu Iceberg lưu gì | Mỗi lần ghi thêm một snapshot |
| 4 | `MERGE INTO` upsert đơn đổi trạng thái; `DELETE` đơn huỷ cũ | Sửa dữ liệu có transaction | Thay cho `partitionOverwriteMode=dynamic` của step 10 |
| 5 | Time travel: `VERSION AS OF`, `TIMESTAMP AS OF`, `CALL ice.system.rollback_to_snapshot` | Đọc và quay lại quá khứ | Đếm dòng trước/sau MERGE |
| 6 | `ALTER TABLE ... ADD COLUMN`, `RENAME COLUMN` | Schema evolution | File cũ vẫn đọc đúng, không viết lại dữ liệu |
| 7 | `ALTER TABLE ... ADD PARTITION FIELD bucket(16, customer_id)` | Partition evolution | Dữ liệu cũ giữ layout cũ, dữ liệu mới theo layout mới |
| 8 | Ghi nhiều batch nhỏ rồi `CALL ice.system.rewrite_data_files`, `expire_snapshots` | Compaction và dọn dẹp | Số file `.files` giảm |
| 9 | Đọc từ StarRocks qua catalog `ice` (`SELECT ... FROM ice.shop.orders`) | Nhiều engine dùng chung một bảng | Thấy cùng snapshot với Spark; sau MERGE ở Spark, StarRocks thấy dữ liệu mới |

**Bài tập:** chạy hai job Spark cùng `MERGE` một lúc và xem commit xung đột được xử lý thế nào; so số file và thời gian đọc của `by_day_bad` (step 07) với bảng Iceberg sau compaction.
