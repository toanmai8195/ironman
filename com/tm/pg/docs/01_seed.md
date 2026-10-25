# Step 01 — Sinh dữ liệu

- **File:** `sql/01_seed.sql` · **Chạy:** `./run.sh step 1` (cần step 00 trước; mất khoảng vài chục giây)
- **Mục đích:** nạp ~600 nghìn dòng bằng thuần SQL để các step sau có dữ liệu đủ lớn cho index/plan khác biệt rõ. Cố ý **chưa tạo index phụ** nào.
- **Docs:** https://www.postgresql.org/docs/current/functions-srf.html (generate_series) · https://www.postgresql.org/docs/current/sql-insert.html

## Nội dung file

| # | Câu lệnh | Dùng để làm gì |
|---|---|---|
| 1 | `CREATE FUNCTION pick(text[])` | Hàm SQL chọn ngẫu nhiên 1 phần tử mảng, dùng khắp file (khai báo `VOLATILE` vì có `random()`) |
| 2 | INSERT `categories` (3 lần) | Cây 3 tầng, id cố định để các step sau tham chiếu |
| 3 | INSERT `customers` ← `generate_series(1, 25000)` | Email/tên giả, 1/20 `city` NULL, tier lệch về `free` |
| 4 | INSERT `products` ← `generate_series(1, 2500)` | Tên/mô tả ghép từ từ vựng (dữ liệu cho FTS); `jsonb_build_object` cho `attrs`; mảng `tags` |
| 5 | INSERT `orders` ← `generate_series(1, 150000)` | `power(random(), 2)` làm phân bố lệch: khách id nhỏ mua rất nhiều; chỉ customer 1..22500 |
| 6 | `UPDATE orders SET shipped_at` | Chỉ đơn shipped/delivered có ngày giao |
| 7 | INSERT `order_items` với `CROSS JOIN LATERAL generate_series` | Mỗi đơn 1-4 dòng; product chỉ 1..2250; subquery có `random()` để mỗi dòng chốt product một lần |
| 8 | `UPDATE orders ... FROM (SELECT sum(line_total) ...)` | Cập nhật `total` bằng UPDATE-FROM (cú pháp riêng của Postgres) |
| 9 | INSERT `reviews ... ON CONFLICT DO NOTHING` | Sinh 27k, trùng cặp (product, customer) bị bỏ qua nên còn ~25k |
| 10 | `ANALYZE` | Cập nhật thống kê để planner có số liệu |
| 11 | 2 SELECT cuối | Đếm dòng từng bảng; kích thước bảng bằng `pg_total_relation_size` |

## Quan sát / bài tập

- Cố ý để dữ liệu "có hình dạng": khách chưa mua (id > 22500), sản phẩm chưa bán (id > 2250), city NULL, phân bố lệch. Các step sau khai thác từng điểm này.
- Vì sao subquery ở mục 7 phải tách riêng khỏi `JOIN products` có `random()` trong điều kiện ON? (Biểu thức volatile trong điều kiện join được tính lại cho từng cặp dòng.)
- Thử `EXPLAIN ANALYZE` câu INSERT ở mục 5 và xem thời gian; sau đó thử thêm index trước khi insert và so sánh (ghi chậm hơn bao nhiêu?).
