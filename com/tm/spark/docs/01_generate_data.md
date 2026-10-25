# Step 01 — Sinh dữ liệu

- **File:** `jobs/01_generate_data.py` · **Chạy:** `./run.sh step 1` (vài chục giây; ghi vào `data/`)
- **Mục đích:** có bộ dữ liệu đủ lớn và có "hình dạng" cho mọi step sau, chỉ dùng Spark (không cần tải gì).
- **Docs:** https://spark.apache.org/docs/latest/sql-data-sources-parquet.html · https://spark.apache.org/docs/latest/sql-data-sources-json.html

## Khái niệm mới

- **Column expression (`F.col`, `F.lit`, `F.when`):** cột trong Spark là một *biểu thức* (không phải giá trị). `F.col("a") * 2` mô tả phép tính, chạy khi có action. `F.lit(x)` là hằng số, `F.when(...).otherwise(...)` là CASE WHEN.
- **`spark.range(n)`:** DataFrame một cột `id` từ 0..n-1 sinh ngay trên các executor, không cần file nguồn; nền tảng để tạo dữ liệu giả.
- **`rand(seed)`:** số ngẫu nhiên [0,1) mỗi dòng; cùng seed + cùng số partition cho cùng kết quả, nên dữ liệu tái lập được.
- **Parquet:** định dạng file dạng cột, nén, có kèm schema và thống kê min/max; mặc định của Spark cho dữ liệu phân tích (so sánh kỹ ở step 07).
- **JSON lines:** mỗi dòng một object JSON, schema không cố định nên dễ có dữ liệu bẩn.
- **Write mode:** `overwrite` ghi đè, `append` thêm, `ignore`, `error` (mặc định, lỗi nếu đã tồn tại).
- **Một thư mục đầu ra = nhiều file `part-*`:** mỗi partition ghi ra một file, nên số file bằng số partition lúc ghi.
- **`explode` + `sequence`:** `explode` biến mảng thành nhiều dòng; kết hợp để nhân một đơn thành 1-4 dòng item.
- **`broadcast` (xuất hiện thoáng qua):** gửi bảng nhỏ tới mọi executor để join không phải shuffle, giải thích đầy đủ ở step 04.

| # | Mục trong file | Làm gì | Quan sát |
|---|---|---|---|
| 1 | `pick(values, seed)` | Chọn giá trị ngẫu nhiên bằng `element_at(array(...), floor(rand*n)+1)` | Lặp giá trị để tạo trọng số; seed cố định nên dữ liệu lặp lại được |
| 2 | `ts(seed)` | Timestamp ngẫu nhiên trong 2 năm bằng epoch giây `cast("timestamp")` | |
| 3 | `customers`, `products` | `spark.range` + `withColumn`; `cast("decimal(12,2)")` cho tiền | `city` NULL cho 1/20 khách |
| 4 | `orders` | `F.when(rand < 0.05, 1)` đẩy 5% đơn về khách 1; `pow(rand, 2)` làm phân bố lệch | Hot key dùng ở step 04 |
| 5 | `order_items` | `explode(sequence(1, n))` mỗi đơn 1-4 dòng, `broadcast` join lấy giá | `line_total = qty * unit_price` |
| 6 | `events_raw` | Thêm ~3% thiếu `user_id`, `unionByName(sample(0.01))` tạo trùng, ghi JSON với `ts` dạng chuỗi | Dữ liệu bẩn cho step 02 và 10 |
| 7 | In kết quả | Số dòng, số file, dung lượng từng dataset | Số file = số partition lúc ghi |

**Bài tập:** đổi `N_ORD` thành 250.000 và chạy lại; xem số file và kích thước thay đổi thế nào. Thử `repartition(1)` trước khi ghi `customers` rồi so sánh.
