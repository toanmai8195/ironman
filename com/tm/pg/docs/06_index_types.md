# Step 06 — Các loại index khác B-tree

- **File:** `sql/06_index_types.sql` · **Chạy:** `./run.sh step 6` (tạo thêm bảng `order_events` 1,5 triệu dòng và `promotions`)
- **Mục đích:** biết loại index nào hợp kiểu dữ liệu/toán tử nào.
- **Docs:** https://www.postgresql.org/docs/current/indexes-types.html · https://www.postgresql.org/docs/current/gin.html · https://www.postgresql.org/docs/current/brin.html · https://www.postgresql.org/docs/current/gist.html

| Loại | Dùng cho | Toán tử tiêu biểu |
|---|---|---|
| GIN | giá trị gồm nhiều phần tử: array, jsonb, tsvector, trigram | `@>`, `&&`, `?`, `@@` |
| BRIN | bảng rất lớn, giá trị tương quan với vị trí vật lý (log, event) | `<`, `>`, `BETWEEN` |
| GiST | range, hình học, nearest-neighbour, exclusion constraint | `&&`, `@>`, `<->` |
| Hash | chỉ so sánh bằng | `=` |

## Các query

| # | Query | Dùng để làm gì | Quan sát |
|---|---|---|---|
| 1 | `tags @> ARRAY['sale','gift']` trước/sau `USING gin (tags)` | Tìm sản phẩm chứa tất cả tag; thêm `&&` (có ít nhất một) | Seq Scan → Bitmap Index Scan |
| 2 | `attrs @> '{"brand":"Acme","color":"red"}'` với `gin (attrs jsonb_path_ops)` | Lọc JSONB theo mẫu | `jsonb_path_ops` nhỏ/nhanh hơn mặc định nhưng chỉ hỗ trợ `@>` |
| 3a | Tạo `order_events` 1,5 triệu dòng append theo thời gian | Dữ liệu hợp BRIN | `pg_stats.correlation` ≈ 1 |
| 3b | `btree(at)` vs `brin(at)` | So kích thước và tốc độ khoảng thời gian 1 ngày | BRIN nhỏ hơn hàng trăm lần; thử lại trên `orders.created_at` (ngẫu nhiên) sẽ thấy BRIN vô dụng |
| 4 | `promotions` với `EXCLUDE USING gist (product_id WITH =, during WITH &&)` | Chặn hai khuyến mãi chồng thời gian cho cùng sản phẩm | Hai khoảng liền kề `[..)` được; khoảng chồng báo lỗi exclusion; `during @> date` dùng được GiST |
| 5 | `USING hash (sku)` | So khớp `=` | Thường b-tree đã đủ, hash ít khi đáng chọn |
| 6 | `pg_stat_user_indexes` | Tổng hợp kích thước các loại index | |

## Bài tập

- So `jsonb_ops` (mặc định) với `jsonb_path_ops`: kích thước và việc hỗ trợ toán tử `?`.
- Thêm `LIMIT 1` cho query BRIN: điều gì xảy ra với số block phải đọc?
- Thiết kế exclusion constraint cho đặt phòng/lịch hẹn trùng giờ.
