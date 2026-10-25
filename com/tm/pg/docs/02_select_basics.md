# Step 02 — SELECT cơ bản

- **File:** `sql/02_select_basics.sql` · **Chạy:** `./run.sh step 2` (chỉ đọc)
- **Mục đích:** lọc, xử lý NULL, tổng hợp, gom nhóm, phân trang. Trả lời câu hỏi nghiệp vụ "doanh thu ra sao, ai mua nhiều, đơn nào kẹt".
- **Docs:** https://www.postgresql.org/docs/current/queries.html · https://www.postgresql.org/docs/current/functions-aggregate.html

## Các query

| # | Query | Dùng để làm gì | Quan sát |
|---|---|---|---|
| 1 | `count(*) FILTER (WHERE city = ...)` ×4 | Cho thấy `<>` bỏ sót NULL, `IS DISTINCT FROM` thì không | `not_hanoi_bo_sot_null` < `not_hanoi_dung` |
| 1b | `coalesce`, `nullif`, `NULLS LAST` | Thay NULL bằng giá trị mặc định / biến giá trị thành NULL / điều khiển vị trí NULL khi sort | |
| 2 | `date_trunc('month')` + `GROUP BY 1` + `FILTER` | Doanh thu, số đơn, đơn delivered theo tháng | `FILTER` gọn hơn `SUM(CASE ...)` |
| 3 | `HAVING sum(total) > 5000` | Lọc **sau** khi gom nhóm (WHERE lọc trước) | Khách chi tiêu cao nhất |
| 4 | `GROUP BY ROLLUP (city, tier)` | Tổng chi tiết + subtotal + grand total trong một câu | Dòng có NULL là dòng tổng hợp; cũng có `GROUPING SETS`, `CUBE` |
| 5 | `DISTINCT ON (customer_id)` | Mỗi khách lấy đơn mới nhất (đặc trưng Postgres) | Cần `ORDER BY` bắt đầu bằng cột trong DISTINCT ON |
| 6 | `CASE` + `GROUP BY 1` | Chia nhóm đơn small/medium/large | |
| 7 | `LIMIT/OFFSET` | Phân trang đơn giản | OFFSET sâu chậm dần, giải ở step 11 |
| 8 | `now() - created_at`, `AT TIME ZONE` | Số học interval, đổi múi giờ | |
| 9 | `status = 'paid' AND created_at < now() - interval '30 days'` | Đơn "kẹt" | Dùng lại để thiết kế partial index ở step 05 |

## Bài tập

- Viết doanh thu theo `city` chỉ tính đơn `delivered`, sắp xếp giảm dần.
- Đổi query 3 thành WHERE: có chạy được không? Vì sao không (aggregate không được dùng trong WHERE)?
- Thay `ROLLUP` bằng `CUBE` và so sánh số dòng.

## Definition of Done

Xong step khi **tất cả** các ô dưới đây đúng; chưa đúng thì chưa sang step sau.

- [ ] `./run.sh step 2` chạy hết, không lỗi.
- [ ] Mục 1: bốn con số `hanoi`, `no_city`, `not_hanoi_bo_sot_null`, `not_hanoi_dung` và bạn giải thích chênh lệch.
- [ ] Phân biệt WHERE và HAVING bằng ví dụ ở mục 3; làm bài tập thử đặt aggregate vào WHERE và đọc lỗi.
- [ ] Đọc được dòng subtotal/grand total trong `ROLLUP` (mục 4).
- [ ] Làm bài tập doanh thu theo `city` chỉ đơn `delivered`.
