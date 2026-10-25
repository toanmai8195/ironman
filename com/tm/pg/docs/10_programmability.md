# Step 10 — View, function, trigger

- **File:** `sql/10_programmability.sql` · **Chạy:** `./run.sh step 10` (tạo view, materialized view, function, procedure, trigger, role; UPDATE 2 đơn)
- **Mục đích:** đóng gói logic ở database: truy vấn dùng lại, cache kết quả, hàm, kiểm toán tự động.
- **Docs:** https://www.postgresql.org/docs/current/sql-createview.html · https://www.postgresql.org/docs/current/rules-materializedviews.html · https://www.postgresql.org/docs/current/plpgsql.html · https://www.postgresql.org/docs/current/triggers.html

## Các query

| # | Đối tượng | Dùng để làm gì | Quan sát |
|---|---|---|---|
| 1 | `VIEW v_customer_spend` | Lưu câu truy vấn (không lưu dữ liệu), đọc như bảng | Chạy lại câu gốc mỗi lần |
| 2 | `MATERIALIZED VIEW mv_daily_revenue` + unique index + `REFRESH ... CONCURRENTLY` | Cache kết quả nặng, làm mới theo lịch | `CONCURRENTLY` không chặn đọc nhưng cần UNIQUE index |
| 3a | `FUNCTION customer_ltv` (`LANGUAGE sql STABLE`) | Hàm vô hướng đơn giản | `STABLE` cho phép planner tối ưu |
| 3b | `FUNCTION top_products ... RETURNS TABLE` (PL/pgSQL) | Hàm trả bảng, tham số mặc định | Gọi như bảng: `SELECT * FROM top_products(5)` |
| 4 | `PROCEDURE cancel_stale_orders` + `COMMIT` trong vòng lặp | Xử lý theo lô, mỗi lô một transaction, không giữ khoá lâu | Procedure (`CALL`) mới được COMMIT bên trong; `SKIP LOCKED` tránh chờ |
| 5 | `TRIGGER orders_status_audit` (`AFTER UPDATE OF status ... WHEN (OLD IS DISTINCT FROM NEW)`) | Ghi log mỗi lần đổi trạng thái đơn | Sau 2 UPDATE, `order_status_log` có 2 dòng |
| 6 | (comment) generated column vs trigger | Giá trị suy ra từ cùng dòng thì dùng GENERATED | |
| 7 | `CREATE ROLE analyst` + `GRANT SELECT` trên view | Cho BI đọc view mà không đụng bảng gốc | Nguyên tắc quyền tối thiểu |

## Bài tập

- Gọi `CALL cancel_stale_orders(700)` và xem `order_status_log` tăng thế nào.
- Viết trigger `BEFORE UPDATE` tự gán `updated_at = now()`.
- Thêm cột `updated_at` vào `mv_daily_revenue` cách làm: view không có nên tính từ `max(created_at)`.
