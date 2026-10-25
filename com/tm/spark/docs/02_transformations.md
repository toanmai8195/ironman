# Step 02 — Biến đổi và làm sạch

- **File:** `jobs/02_transformations.py` · **Chạy:** job step 2 (cần step 1; **ghi `/data/events`** cho các step sau)
- **Mục đích:** các phép biến đổi hằng ngày và quy trình làm sạch dữ liệu bẩn.
- **Docs:** https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/functions.html

## Khái niệm mới

- **`withColumn` / `select` / `drop`:** thêm, chọn, bỏ cột. Không sửa DataFrame cũ mà trả về DataFrame mới.
- **Toán tử cột:** dùng `&`, `|`, `~` thay `and/or/not` của Python, và **phải bọc ngoặc** mỗi điều kiện: `(a > 1) & (b == 2)`.
- **NULL ba trị:** so sánh với NULL cho ra NULL (không đúng cũng không sai) nên `filter` loại dòng đó. Dùng `isNull()`, `eqNullSafe()`, `coalesce()`.
- **`na.fill` / `na.drop`:** điền hoặc bỏ dòng NULL, có thể giới hạn bằng `subset=`.
- **Kiểu phức hợp:** `array`, `struct`, `map`. `explode` tách mảng thành dòng (bỏ dòng mảng rỗng/NULL); `explode_outer` giữ lại.
- **Đọc file với `mode`:** `PERMISSIVE` (mặc định, dòng hỏng thành NULL + giữ nguyên văn trong `_corrupt_record`), `DROPMALFORMED` (bỏ dòng hỏng), `FAILFAST` (lỗi ngay).
- **Schema khi đọc:** truyền schema vào `read.schema(...)` nhanh hơn và an toàn hơn `inferSchema` (không phải quét dữ liệu đoán kiểu).
- **`dropDuplicates(cols)`:** bỏ trùng theo cột; là wide transformation (shuffle theo các cột đó), giữ một bản bất kỳ. Cần giữ bản mới nhất thì dùng window (step 05, 10).
- **`to_timestamp`, `to_date`, `date_trunc`:** chuyển chuỗi thành thời gian và cắt về mốc (tháng, ngày). Múi giờ theo `spark.sql.session.timeZone`.

| # | Mục trong file | Làm gì | Quan sát |
|---|---|---|---|
| 1 | `select`, `filter`, `withColumn`, `when/otherwise`, `selectExpr` | Cột tuổi đơn, nhóm recent/mid/old; viết bằng biểu thức SQL | `&` `|` `~` thay `and/or/not`, nhớ bọc ngoặc |
| 2 | Tỉ lệ NULL mỗi cột, `na.fill`, `na.drop(subset=)` | Kiểm tra và xử lý thiếu dữ liệu | Dòng một lệnh cho tỉ lệ NULL của mọi cột |
| 3 | `regexp_extract`, `split`, `lower` | Xử lý chuỗi | |
| 4 | `date_trunc`, `dayofweek`, `date_format`, `interval` | Xử lý ngày giờ | Múi giờ session đặt UTC trong `lib/common.py` |
| 5 | Array: `size`, `array_contains`, `explode_outer`, `struct` | Làm việc với kiểu phức hợp | `explode` bỏ dòng mảng rỗng, `explode_outer` giữ |
| 6 | JSON lỗi: `PERMISSIVE`, `DROPMALFORMED`, `FAILFAST` | Ba chế độ xử lý dòng hỏng | PERMISSIVE giữ dòng lỗi trong `_corrupt_record` để điều tra |
| 7 | Làm sạch `events_raw`: schema tường minh → `to_timestamp` → `dropDuplicates(["event_id"])` → bỏ thiếu `user_id` → ghi parquet | Pipeline làm sạch thật | In số dòng ở mỗi bước; `dropDuplicates` gây shuffle |

**Bài tập:** thay `dropDuplicates` bằng window `row_number()` giữ bản có `ts` mới nhất; so sánh plan. Đếm sự kiện bị bỏ theo từng lý do.

## Definition of Done

Xong step khi **tất cả** các ô dưới đây đúng; chưa đúng thì chưa sang step sau.

- [ ] job step 2 chạy xong và có `/data/events`.
- [ ] Số dòng in ở mục 7 đúng quan hệ: raw > sau dedupe > sau bỏ thiếu `user_id`, và bạn giải thích được từng chênh lệch.
- [ ] Cho ra kết quả của 3 mode đọc JSON lỗi và nói mode nào giữ lại dòng hỏng để điều tra.
- [ ] Giải thích được vì sao `city != 'Hanoi'` mất dòng NULL và viết được bản đúng.
- [ ] Làm bài tập thay `dropDuplicates` bằng window giữ bản mới nhất.
