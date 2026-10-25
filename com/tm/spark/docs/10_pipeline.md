# Step 10 — Pipeline bronze → silver → gold

- **File:** `jobs/10_pipeline.py` · **Chạy:** job step 10 (cần step 1; ghi `/data/lake/{bronze,silver,gold}`, xoá và tạo lại mỗi lần)
- **Mục đích:** gộp mọi kỹ thuật thành một pipeline hoàn chỉnh theo kiến trúc medallion.
- **Docs:** https://spark.apache.org/docs/latest/sql-data-sources-parquet.html#partition-discovery · https://spark.apache.org/docs/latest/sql-data-sources-load-save-functions.html

## Khái niệm mới

- **Medallion (bronze/silver/gold):** chia dữ liệu thành ba lớp. *Bronze* giữ dữ liệu thô nguyên trạng để có thể nạp lại; *silver* đã làm sạch, đúng kiểu, bỏ trùng; *gold* là bảng tổng hợp theo nhu cầu nghiệp vụ.
- **Metadata nạp:** thêm `_ingested_at`, `_source_file` (`input_file_name()`) vào bronze để truy vết dòng đến từ file nào, lúc nào.
- **Dedupe giữ bản mới nhất:** `row_number()` trên `Window.partitionBy(khoá).orderBy(desc(thời gian nạp))` rồi giữ `rn = 1`; khác `dropDuplicates` ở chỗ chọn được bản nào giữ lại.
- **Quality gate:** bước kiểm tra kỳ vọng (duy nhất, không NULL, giá trị hợp lệ, khoảng thời gian) và dừng pipeline nếu vi phạm, để dữ liệu sai không lan xuống gold.
- **Idempotent / incremental:** chạy lại cho kết quả giống nhau, và chỉ xử lý phần cần (một ngày) thay vì toàn bộ.
- **`partitionOverwriteMode=dynamic`:** `mode("overwrite")` mặc định xoá *cả bảng* rồi ghi; ở chế độ dynamic chỉ ghi đè các partition có xuất hiện trong dữ liệu ghi, các partition khác giữ nguyên.
- **`repartition(col)` trước `partitionBy(col)`:** gom dữ liệu cùng ngày về một task để mỗi ngày chỉ ra một vài file (xem small files ở step 07).

| Lớp | Nội dung | Kỹ thuật dùng |
|---|---|---|
| Bronze | Event thô + `_ingested_at`, `_source_file`, `ingest_date` | Schema tường minh, `input_file_name()`, `partitionBy("ingest_date")` |
| Silver | Ép kiểu, dedupe giữ bản mới nhất, bỏ dòng hỏng | `row_number()` window, `to_timestamp`, `repartition("event_date")` + `partitionBy` |
| Quality gate | 4 kiểm tra: `event_id` duy nhất, không NULL `user_id`, `event_type` hợp lệ, `ts` trong khoảng | `assert all(checks)` làm pipeline dừng nếu dữ liệu sai |
| Gold 1 | `daily_funnel`: ngày × danh mục × thiết bị (views, clicks, carts, purchases, buy_rate) | broadcast join `products`, conditional aggregate |
| Gold 2 | `daily_revenue`: ngày × danh mục (doanh thu, số đơn) | join `orders` ⨝ `order_items` ⨝ `products` |
| Incremental | Nạp lại một ngày (`2025-03-15`) | `spark.sql.sources.partitionOverwriteMode=dynamic`: chỉ ghi đè partition có trong dữ liệu |
| Kết quả | Top 5 ngày doanh thu, buy_rate theo danh mục | |

**Bài tập:** thêm bảng Gold thứ ba "top sản phẩm xem nhiều nhưng ít mua"; chia bài thành hàm có tham số `--date` để chạy incremental mỗi ngày; bỏ `partitionOverwriteMode=dynamic` và xem điều gì xảy ra với các ngày còn lại (toàn bảng bị ghi đè).

## Definition of Done

Xong step khi **tất cả** các ô dưới đây đúng; chưa đúng thì chưa sang step sau.

- [ ] job step 10 chạy hết và cả 4 dòng quality gate in `PASS`.
- [ ] `/data/lake/` có đủ `bronze`, `silver`, `gold` với các thư mục partition.
- [ ] Phần incremental: số dòng trước và sau bằng nhau, bạn giải thích vì sao các ngày khác không bị mất.
- [ ] Thử bỏ `partitionOverwriteMode=dynamic` và quan sát hậu quả.
- [ ] Vẽ lại được luồng bronze → silver → gold và nói mỗi lớp giữ gì.
