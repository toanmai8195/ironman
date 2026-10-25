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
| customers | 25.000 | `city` có NULL; 2.500 khách cuối chưa mua gì (LEFT JOIN/anti-join) |
| products | 2.500 | `attrs jsonb`, `tags text[]`, mô tả để full-text search; 250 sản phẩm cuối chưa bán |
| orders | 150.000 | phân bố lệch (vài khách VIP rất nhiều đơn), enum `order_status` |
| order_items | ~375.000 | khoá phức hợp, cột generated `line_total` |
| reviews | ~25.000 | UNIQUE (product, customer) cho upsert |

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

## Checklist

Tick khi trả lời được các câu tự kiểm tra của step đó mà không cần nhìn doc.

- [ ] **00 Schema**: PK, UNIQUE, FK, CHECK khác nhau thế nào và cái nào tự tạo index? Enum và domain dùng khi nào? `GENERATED ALWAYS` khác `BY DEFAULT`?
- [ ] **01 Seed**: `generate_series` + `LATERAL` sinh nhiều dòng thế nào? Vì sao `random()` trong điều kiện JOIN gây sai? `ON CONFLICT DO NOTHING` làm gì?
- [ ] **02 SELECT**: Vì sao `<> 'x'` bỏ sót NULL, `IS DISTINCT FROM` thì không? WHERE khác HAVING ra sao? `ROLLUP` và `DISTINCT ON` cho kết quả gì? Vì sao OFFSET sâu chậm?
- [ ] **03 JOIN**: Kể đủ 6 loại join và khi nào dùng. Vì sao điều kiện bảng phải đặt trong `ON` của LEFT JOIN? `NOT IN` với NULL sai ở đâu? Fan-out là gì?
- [ ] **04 CTE và window**: CTE khác subquery và view ra sao? Viết được recursive CTE duyệt cây. `rank`, `dense_rank`, `row_number` khác nhau thế nào? Frame `ROWS` khác `RANGE` ra sao?
- [ ] **05 B-tree**: Đọc plan nhận ra Seq Scan, Index Scan, Bitmap, Index Only Scan. Leftmost prefix là gì? Khi nào dùng partial, expression, covering index? Index làm chậm ghi vì sao?
- [ ] **06 Loại index**: GIN, BRIN, GiST, Hash mỗi loại hợp dữ liệu nào? BRIN cần điều kiện gì? `EXCLUDE` chặn được gì mà UNIQUE không chặn được?
- [ ] **07 Full Text Search**: `tsvector` và `tsquery` là gì? `websearch_to_tsquery` tiện chỗ nào? Trọng số A/B ảnh hưởng xếp hạng ra sao? FTS và `pg_trgm` khác nhau thế nào, tiếng Việt xử lý ra sao?
- [ ] **08 JSONB**: `->` khác `->>`, `@>` khác `?`. GIN và expression index mỗi cái phục vụ truy vấn nào? Khi nào dùng cột thật thay JSONB?
- [ ] **09 Transaction**: MVCC tạo phiên bản dòng thế nào và `ctid` đổi ra sao khi UPDATE? Ba mức cô lập khác nhau chỗ nào, lỗi `40001` xử lý ra sao? `SKIP LOCKED` giải quyết gì? Tránh deadlock bằng cách nào?
- [ ] **10 Lập trình**: View khác materialized view ra sao? `CONCURRENTLY` cần gì? Function khác procedure ở khả năng nào? Khi nào dùng generated column thay trigger?
- [ ] **11 Performance**: Đọc `EXPLAIN ANALYZE`: ước lượng lệch thực tế nghĩa là gì và sửa thế nào? OFFSET khác keyset ở đâu? Partition pruning lợi gì? VACUUM khác VACUUM FULL ra sao? Dùng `pg_stat_statements` để tìm gì?
