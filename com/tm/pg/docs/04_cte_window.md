# Step 04 — CTE và Window function

- **File:** `sql/04_cte_window.sql` · **Chạy:** `./run.sh step 4`
- **Mục đích:** chia truy vấn phức tạp thành bước dễ đọc, duyệt cây, và tính trên "cửa sổ" dòng (xếp hạng, so với kỳ trước, cộng dồn) mà không gộp dòng.
- **Docs:** https://www.postgresql.org/docs/current/queries-with.html · https://www.postgresql.org/docs/current/tutorial-window.html · https://www.postgresql.org/docs/current/functions-window.html
- **Cảnh báo:** mục 4 **xoá** vài review rating 1 cũ sang bảng `archived_reviews`.

## Các query

| # | Query | Dùng để làm gì | Quan sát |
|---|---|---|---|
| 1 | `WITH spend AS (...)` | Chi tiêu trung bình theo tier | Từ PG12 CTE dùng một lần được inline; ép bằng `MATERIALIZED`/`NOT MATERIALIZED` |
| 2a | `WITH RECURSIVE tree` | Duyệt cây danh mục, sinh `depth` và `path` | Phần neo (gốc) `UNION ALL` phần đệ quy |
| 2b | `WITH RECURSIVE up` | Đẩy mỗi danh mục lên gốc rồi cộng doanh thu theo nhánh | Dạng "closure" của cây |
| 3a | `row_number / rank / dense_rank OVER w` + `WINDOW w AS (...)` | Xếp hạng giá trong từng danh mục | Khác nhau khi đồng hạng |
| 3b | `row_number() ... WHERE rn <= 2` | Top-N mỗi nhóm (so với LATERAL ở step 03) | Cần bọc subquery vì không lọc được window trong WHERE |
| 3c | `lag`, `sum() OVER (ORDER BY)`, `avg() ... ROWS BETWEEN 2 PRECEDING` | Doanh thu tháng, % tăng so với tháng trước, cộng dồn, trung bình trượt 3 tháng | |
| 3d | `ntile(4)`, `percentile_cont(ARRAY[...]) WITHIN GROUP` | Tứ phân vị khách hàng, P50/P90/P99 giá trị đơn | Ordered-set aggregate |
| 3e | `RANGE` mặc định vs `ROWS` | Tổng cộng dồn trên giá trị trùng | RANGE gom các dòng đồng hạng làm một |
| 4 | `WITH moved AS (DELETE ... RETURNING *) INSERT ...` | Di chuyển dữ liệu sang bảng lưu trữ trong một câu nguyên tử | Data-modifying CTE |

## Bài tập

- Thêm cột `is_leaf` vào query 2a (danh mục không có con).
- Tính "khách quay lại": với mỗi đơn, số ngày kể từ đơn trước của cùng khách (`lag(created_at) OVER (PARTITION BY customer_id ORDER BY created_at)`).
- Viết lại 3b bằng `DISTINCT ON` khi N = 1, so sánh plan.
