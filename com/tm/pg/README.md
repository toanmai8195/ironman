# Học PostgreSQL qua bài toán "Ironshop"

Một cửa hàng online nhỏ làm bài toán xuyên suốt. Mỗi step thêm một nhóm tính năng của SQL/Postgres lên **cùng một bộ dữ liệu**, nên kết quả step sau dựa vào step trước (ví dụ step 05 tạo index, step 11 đo lại).

Tham khảo: https://www.postgresql.org/docs/19/index.html (link trong doc dùng `/docs/current/` để luôn đúng bản mới nhất).

## Chạy

```bash
cd com/tm/pg
./run.sh up          # Postgres 18 ở localhost:5435 (user/pass/db: lab/lab/lab), tự bật pg_stat_statements
./run.sh step 0      # chạy 1 step (echo từng câu lệnh + kết quả)
./run.sh all         # chạy tuần tự 00 → 11 (step 00 và 01 reset dữ liệu)
./run.sh psql        # vào psql để tự gõ / chạy 2 session cho step 09
./run.sh reset       # xoá volume, làm lại từ đầu
```

Cách học khuyến nghị: mở file `.sql` ở editor, đọc doc của step, chạy từng câu trong `./run.sh psql` (hoặc DBeaver: `postgresql://lab:lab@localhost:5435/lab`) rồi mới chạy cả file để đối chiếu. Bật `\timing on` để thấy thời gian.

## Mô hình dữ liệu

```
categories (cây, parent_id) ◄── products ◄── order_items ──► orders ──► customers
                                   ▲                                       ▲
                                   └────────────── reviews ────────────────┘
```

| Bảng | Số dòng | Ghi chú để học |
|---|---|---|
| categories | 16 | cây 3 tầng: self join, recursive CTE |
| customers | 50.000 | `city` có NULL; 5.000 khách cuối chưa mua gì (LEFT JOIN/anti-join) |
| products | 5.000 | `attrs jsonb`, `tags text[]`, mô tả để full-text search; 500 sản phẩm cuối chưa bán |
| orders | 300.000 | phân bố lệch (vài khách VIP rất nhiều đơn), enum `order_status` |
| order_items | ~750.000 | khoá phức hợp, cột generated `line_total` |
| reviews | ~50.000 | UNIQUE (product, customer) cho upsert |

## Lộ trình

| Step | File SQL | Chủ đề | Doc |
|---|---|---|---|
| 00 | `sql/00_schema.sql` | DDL, kiểu dữ liệu, ràng buộc | [docs/00_schema.md](docs/00_schema.md) |
| 01 | `sql/01_seed.sql` | Sinh dữ liệu bằng SQL | [docs/01_seed.md](docs/01_seed.md) |
| 02 | `sql/02_select_basics.sql` | SELECT, NULL, GROUP BY, ROLLUP, DISTINCT ON | [docs/02_select_basics.md](docs/02_select_basics.md) |
| 03 | `sql/03_joins.sql` | Mọi loại JOIN, LATERAL, semi/anti join | [docs/03_joins.md](docs/03_joins.md) |
| 04 | `sql/04_cte_window.sql` | CTE, recursive, window function | [docs/04_cte_window.md](docs/04_cte_window.md) |
| 05 | `sql/05_indexes.sql` | B-tree: đơn, phức hợp, partial, expression, covering | [docs/05_indexes.md](docs/05_indexes.md) |
| 06 | `sql/06_index_types.sql` | GIN, BRIN, GiST + EXCLUDE, Hash | [docs/06_index_types.md](docs/06_index_types.md) |
| 07 | `sql/07_full_text_search.sql` | Full Text Search, pg_trgm, unaccent | [docs/07_full_text_search.md](docs/07_full_text_search.md) |
| 08 | `sql/08_jsonb.sql` | JSONB, SQL/JSON path | [docs/08_jsonb.md](docs/08_jsonb.md) |
| 09 | `sql/09_transactions.sql` | Transaction, MVCC, khoá, upsert, SKIP LOCKED | [docs/09_transactions.md](docs/09_transactions.md) |
| 10 | `sql/10_programmability.sql` | View, materialized view, function, trigger | [docs/10_programmability.md](docs/10_programmability.md) |
| 11 | `sql/11_performance.sql` | EXPLAIN, statistics, partition, VACUUM, pg_stat_statements | [docs/11_performance.md](docs/11_performance.md) |

## Lưu ý

- Compose riêng (`com/tm/pg/docker-compose.yml`), cổng 5435, không đụng Postgres CDC (5434) của thử nghiệm Debezium.
- Cấu hình Postgres cố ý gần mặc định để số đo ở step 05/11 phản ánh đúng thay đổi của query/index, không phải do tuning.
- Step 04, 09, 10, 11 có ghi (UPDATE, tạo bảng phụ). Chạy lại `./run.sh step 0` rồi `step 1` để reset dữ liệu.
- Step 09 có phần cần **2 session psql** (ghi chú trong file bằng `[2 SESSION]`), `run.sh` không tự chạy được phần đó.
