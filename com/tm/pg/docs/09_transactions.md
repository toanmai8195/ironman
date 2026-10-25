# Step 09 — Transaction, MVCC, khoá

- **File:** `sql/09_transactions.sql` · **Chạy:** `./run.sh step 9` cho phần chạy được một mình; phần `[2 SESSION]` phải gõ tay ở **hai terminal** `./run.sh psql`
- **Mục đích:** hiểu Postgres xử lý đồng thời thế nào (MVCC) và dùng đúng khoá/upsert/hàng đợi.
- **Docs:** https://www.postgresql.org/docs/current/mvcc.html · https://www.postgresql.org/docs/current/transaction-iso.html · https://www.postgresql.org/docs/current/explicit-locking.html · https://www.postgresql.org/docs/current/sql-insert.html#SQL-ON-CONFLICT

## Các query

| # | Query | Dùng để làm gì | Quan sát |
|---|---|---|---|
| 1 | `BEGIN; ... SAVEPOINT; ROLLBACK TO; ROLLBACK;` | Huỷ toàn bộ / huỷ một phần | Sau ROLLBACK dữ liệu không đổi |
| 2 | `SELECT ctid, xmin, xmax` trước/sau `UPDATE` | Thấy MVCC: UPDATE tạo phiên bản mới | `ctid` đổi; bản cũ là dead tuple chờ VACUUM |
| 3 | `INSERT ... ON CONFLICT DO UPDATE ... RETURNING (xmax = 0)` | Upsert nguyên tử, biết vừa insert hay update | Không race như SELECT-rồi-INSERT |
| 4 | Bảng `stock` + `UPDATE ... WHERE qty >= 3 RETURNING` | Trừ kho an toàn không cần khoá thủ công | Lần hai trả 0 dòng nghĩa là hết hàng |
| 5 | **[2 SESSION]** READ COMMITTED vs REPEATABLE READ vs SERIALIZABLE | Xem non-repeatable read và lỗi serialization | Mã lỗi `40001` phải retry ở ứng dụng |
| 6 | **[2 SESSION]** `SELECT ... FOR UPDATE` | Session 2 treo chờ session 1; xem bằng `pg_stat_activity` | `wait_event_type = Lock` |
| 7 | Bảng `jobs` + `FOR UPDATE SKIP LOCKED` | Hàng đợi: nhiều worker lấy việc không giẫm nhau | Worker khác bỏ qua dòng đang bị khoá thay vì chờ |
| 8 | Mô tả deadlock (comment) | Hiểu vì sao xảy ra và cách tránh | Luôn khoá theo cùng thứ tự; lỗi `40P01` |
| 9 | `pg_try_advisory_lock(42)` | Khoá do ứng dụng quy ước (chỉ một cron chạy) | |
| 10 | `BEGIN; ALTER TABLE ...; ROLLBACK;` | DDL cũng nằm trong transaction | Migration atomic, không dở dang |

## Bài tập

- Làm lại mục 5 với `SERIALIZABLE`, tái hiện *write skew* (hai transaction cùng đọc tổng rồi cùng ghi).
- Tái hiện deadlock bằng hai session, đọc log của Postgres: `docker logs ironman-pglab`.
- Giữ một transaction mở lâu rồi chạy `VACUUM` xem `n_dead_tup` có giảm không (transaction treo chặn dọn dẹp).
