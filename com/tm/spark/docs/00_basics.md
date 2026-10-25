# Step 00 — Nền tảng: SparkSession, DataFrame, lazy evaluation

- **File:** `jobs/00_basics.py` · **Chạy:** `./run.sh step 0` (không cần dữ liệu)
- **Mục đích:** hiểu mô hình của Spark trước khi viết job thật: DataFrame là *kế hoạch*, chỉ action mới chạy; shuffle là chi phí chính.
- **Docs:** https://spark.apache.org/docs/latest/sql-programming-guide.html · https://spark.apache.org/docs/latest/rdd-programming-guide.html

## Khái niệm mới

- **Driver / Executor:** driver là tiến trình chạy code Python của bạn và lập kế hoạch; executor là các tiến trình làm việc thật trên dữ liệu. Ở local mode cả hai nằm trong một JVM (`local[4]` = 4 luồng làm executor).
- **SparkSession:** cửa vào của mọi chương trình Spark (`spark = SparkSession.builder...getOrCreate()`); từ đó đọc dữ liệu, chạy SQL, đặt cấu hình.
- **DataFrame:** bảng phân tán có tên cột và kiểu. Nó *không chứa dữ liệu* mà là mô tả phép tính (logical plan). Bất biến: mỗi phép biến đổi trả về DataFrame mới.
- **Schema:** danh sách (tên cột, kiểu, nullable). Khai báo tường minh (StructType hoặc DDL string) tránh việc Spark phải đọc dữ liệu để đoán.
- **Transformation vs Action:** transformation (`filter`, `select`, `groupBy`...) chỉ dựng kế hoạch; action (`count`, `show`, `collect`, `write`) mới kích hoạt chạy. Đó là **lazy evaluation**, cho phép Spark tối ưu cả chuỗi phép tính trước khi chạy.
- **Partition:** một mảnh dữ liệu; mỗi partition được xử lý bởi một **task**. Số partition quyết định mức song song.
- **Narrow vs Wide transformation:** narrow (`filter`, `select`) xử lý từng partition độc lập; wide (`groupBy`, `join`) cần gom dữ liệu cùng khoá về cùng chỗ, gọi là **shuffle** (ghi đĩa + truyền mạng, chi phí chính của Spark). Plan hiển thị là `Exchange`.
- **Job / Stage / Task:** một action sinh ra job; job chia thành stage ở mỗi ranh giới shuffle; stage gồm nhiều task (mỗi task một partition).
- **Catalyst:** bộ tối ưu của Spark SQL. Biến plan qua các pha parsed → analyzed → optimized → physical (đẩy filter xuống, bỏ cột thừa, chọn chiến lược join...).
- **Spark UI:** giao diện theo dõi job tại http://localhost:4040 khi job còn sống (xem step 08).

| # | Mục trong file | Làm gì | Quan sát |
|---|---|---|---|
| 1 | `createDataFrame` suy luận vs `StructType` vs DDL string | Ba cách khai báo schema | Khai báo tường minh tránh quét dữ liệu để đoán kiểu khi đọc file |
| 2 | `spark.range(10M).filter().withColumn()` rồi `count()` | Lazy evaluation | Chưa có job nào cho tới khi gọi action (xem Spark UI) |
| 3 | `explain()` trước/sau `groupBy` | Narrow vs wide transformation | Chỉ wide mới có `Exchange hashpartitioning` (shuffle) |
| 4 | `explain(mode="extended")` | Parsed → Analyzed → Optimized → Physical plan | Đây là pipeline của Catalyst |
| 5 | `rdd.getNumPartitions()`, `glom().map(len)` | Partition = đơn vị song song | Số partition sau shuffle = `spark.sql.shuffle.partitions` |
| 6 | `limit(3).collect()` | Vì sao không `collect()` tập lớn | Toàn bộ dữ liệu về driver gây OOM |
| 7 | `select`, `coalesce`, `!=` với NULL, `eqNullSafe` | Biểu thức cột và NULL | `city != 'Hanoi'` loại cả dòng NULL (như SQL) |

**Bài tập:** đổi `spark.sql.shuffle.partitions` thành 2 rồi xem lại mục 5; thử `big.rdd.glom()` với `repartition(3)` và so kích thước partition.
