# Step 05 — B-tree index

- **File:** `sql/05_indexes.sql` · **Chạy:** `./run.sh step 5`
- **Mục đích:** học tạo index đúng chỗ bằng cách **đo trước/sau**. Mỗi nhóm: chạy `EXPLAIN (ANALYZE, BUFFERS)` → tạo index → chạy lại.
- **Docs:** https://www.postgresql.org/docs/current/indexes.html · https://www.postgresql.org/docs/current/using-explain.html
- **Cách đọc plan:** `Seq Scan` đọc cả bảng · `Index Scan` đi index rồi đọc heap · `Bitmap Heap Scan` gom vị trí rồi đọc heap theo block · `Index Only Scan` không chạm heap · chú ý `Execution Time`, `Buffers: shared hit/read`, `Rows Removed by Filter`.
- File tự dọn index của chính nó ở đầu nên chạy lại được.

## Các query

| # | Index | Query đo | Quan sát |
|---|---|---|---|
| 1 | (chưa có) | `WHERE customer_id = 123` | Seq Scan 150k dòng: FK không tự có index |
| 2 | `idx_orders_customer(customer_id)` | cùng query; thêm `customer_id <= 20000` | Index Scan nhanh hơn nhiều; lấy quá nhiều dòng thì planner chuyển Bitmap/Seq vì index không luôn thắng |
| 3 | `idx_orders_customer_created(customer_id, created_at DESC)` | `WHERE customer_id=? ORDER BY created_at DESC LIMIT 5`; rồi chỉ lọc `created_at` | Không còn node Sort; index phức hợp không giúp khi chỉ lọc cột thứ hai (leftmost prefix). Index đơn ở mục 2 giờ thừa |
| 4 | **Partial** `idx_orders_pending(created_at) WHERE status='pending'` | đơn pending quá cũ | Nhỏ hơn index đầy đủ rất nhiều (so bằng `pg_relation_size`); chỉ dùng khi query chứa điều kiện khớp predicate |
| 5 | **Expression** `idx_customers_lower_email(lower(email))` | `WHERE lower(email) = ...` | Trước: Seq Scan (hàm bọc cột làm index thường vô dụng). Sau: Index Scan |
| 6 | **Covering** `idx_orders_cover(customer_id) INCLUDE (total, status)` + `VACUUM` | chỉ chọn 3 cột trong index | `Index Only Scan`, `Heap Fetches: 0` (cần visibility map sạch nên phải VACUUM) |
| 7 | (dùng index ở mục 3) | `ORDER BY created_at DESC LIMIT 1` cho 1 khách | Đọc đúng 1 entry rồi dừng |
| 8 | — | `pg_stat_user_indexes` | Kích thước từng index và `idx_scan`; `idx_scan = 0` lâu ngày là ứng viên DROP |
| 8b | — | `CREATE TEMP TABLE ... INCLUDING ALL` + INSERT 50k | Đo chi phí ghi; DROP bớt index rồi chạy lại để thấy khác biệt |
| 9 | `CREATE INDEX CONCURRENTLY idx_reviews_product` | — | Không khoá ghi, dùng cho production; không chạy được trong transaction |

## Bài tập

- Đổi thứ tự cột thành `(created_at, customer_id)` và xem query mục 3 còn dùng được không.
- Tìm index trùng/thừa trong `orders` bằng `pg_stat_user_indexes` + `pg_indexes`.
- Query `WHERE customer_id::text = '123'` có dùng index không? Vì sao (ép kiểu cột làm mất index)?
