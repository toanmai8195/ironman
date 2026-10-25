# Step 08 — JSONB

- **File:** `sql/08_jsonb.sql` · **Chạy:** `./run.sh step 8` (sửa nhẹ `attrs` của product 1 và 2)
- **Mục đích:** dùng `products.attrs` làm thuộc tính linh hoạt; biết truy cập, lọc, sinh, sửa, index và khi nào *không* nên dùng JSONB.
- **Docs:** https://www.postgresql.org/docs/current/datatype-json.html · https://www.postgresql.org/docs/current/functions-json.html

## Các query

| # | Query | Dùng để làm gì | Quan sát |
|---|---|---|---|
| 1 | `->`, `->>`, `#>>` | Lấy giá trị: jsonb / text / theo đường dẫn; ép kiểu `(...)::int` | `->` trả jsonb nên còn dấu nháy |
| 2 | `@>`, `?`, `@?` (jsonpath), `jsonb_path_query` | Lọc theo mẫu, theo key, theo điều kiện số (`warranty_months >= 24`) | |
| 3 | `GROUP BY attrs ->> 'brand'` | Thống kê theo giá trị trong JSON | |
| 4 | `jsonb_build_object` + `jsonb_agg(... ORDER BY)` | Dựng response API của một đơn kèm các dòng từ bảng quan hệ | |
| 5 | `jsonb_each`, `unnest(tags)` | Bung JSON/array thành dòng | |
| 6 | `jsonb_set`, `\|\|`, `-` | Sửa 1 field, gộp, xoá key | UPDATE ghi lại cả giá trị jsonb (không sửa tại chỗ) |
| 7 | Expression index `((attrs ->> 'brand'))` | Lọc 1 key hay dùng | Trước: Seq Scan; sau: Bitmap Index Scan. GIN (step 06) hợp cho `@>`/`?` tổng quát |
| 8 | `pg_column_size` jsonb vs text | So kích thước | Cân nhắc JSONB vs cột thật |

Khi nào dùng: JSONB cho thuộc tính thay đổi theo loại, ít join. Cột thật khi cần FK/CHECK/NOT NULL, lọc/join thường xuyên (planner có thống kê tốt cho cột thật; key trong JSONB ước lượng kém).

## Bài tập

- Chuyển `brand` thành cột thật `products.brand` bằng `ALTER TABLE ... ADD COLUMN ... GENERATED ALWAYS AS ((attrs->>'brand')) STORED` và so sánh plan.
- Thêm `CHECK (jsonb_typeof(attrs) = 'object')`.
- Viết query tìm sản phẩm có `warranty_months` cao nhất mỗi brand.
