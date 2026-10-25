# Step 11 — Performance

- **File:** `sql/11_performance.sql` · **Chạy:** `./run.sh step 11` (tạo `orders_part`, `bloat_demo`, thêm một index và một extended statistic; cần step 05 để so sánh)
- **Mục đích:** đọc plan, hiểu planner dựa vào gì, và các kỹ thuật tăng tốc thường gặp.
- **Docs:** https://www.postgresql.org/docs/current/performance-tips.html · https://www.postgresql.org/docs/current/using-explain.html · https://www.postgresql.org/docs/current/ddl-partitioning.html · https://www.postgresql.org/docs/current/routine-vacuuming.html · https://www.postgresql.org/docs/current/pgstatstatements.html

## Các query

| # | Query | Dùng để làm gì | Quan sát |
|---|---|---|---|
| 1 | `EXPLAIN (ANALYZE, BUFFERS)` join + group 90 ngày gần nhất | Đọc plan thật | So `rows` ước lượng với `actual rows`; `Buffers: hit/read` |
| 2 | `pg_stats` (`n_distinct`, `null_frac`, `correlation`, `most_common_vals`) | Thống kê planner dùng | `correlation` cao thì index scan/BRIN rẻ |
| 3 | `CREATE STATISTICS (dependencies, mcv)` trên `city, tier` | Sửa ước lượng sai khi hai cột phụ thuộc nhau | `EXPLAIN` trước/sau; ước lượng sát thực tế hơn |
| 4 | `SET enable_hashjoin=off; enable_mergejoin=off` | Ép Nested Loop để so với Hash Join | Nested Loop chậm hơn với tập lớn; `RESET` sau khi xong |
| 5 | `SET work_mem` 64kB vs 64MB | Sort tràn đĩa | `Sort Method: external merge Disk` so với `quicksort Memory` |
| 6 | OFFSET 100000 vs keyset `(created_at, id) < (...)` + index | Phân trang sâu | OFFSET phải đọc rồi bỏ 100k dòng, keyset nhảy thẳng bằng index |
| 7 | `customer_id = ANY (ARRAY[...])` | Thay N+1 query bằng một câu | Giảm round trip |
| 8 | `reltuples` vs `count(*)` | Đếm xấp xỉ so với đếm chính xác | MVCC buộc `count(*)` phải quét |
| 9 | `orders_part` PARTITION BY RANGE theo tháng | Partition pruning | `EXPLAIN` chỉ chạm vài partition; xoá dữ liệu cũ bằng `DROP/DETACH PARTITION` |
| 10 | `bloat_demo`: UPDATE hết → `VACUUM` → `VACUUM FULL` | Bloat từ MVCC | Bảng phình ~2 lần; VACUUM không trả đĩa, VACUUM FULL trả nhưng khoá bảng |
| 11 | `pg_stat_statements` top theo `total_exec_time` | Tìm câu tốn nhất toàn hệ thống | Cho thấy chính các query bạn vừa chạy |
| 12 | `pg_statio_user_tables`, `pg_stat_user_tables` | Cache hit ratio, bảng bị seq scan nhiều | |
| 13 | (checklist trong comment) | Quy trình xử lý query chậm | EXPLAIN → thiếu index/hàm bọc cột → thống kê → work_mem → bloat → round trip |

## Bài tập

- Chạy cả bộ step 02 đến 04 rồi xem lại `pg_stat_statements`; tìm câu có `mean_ms` cao nhất.
- Thử `EXPLAIN (ANALYZE)` mục 1 với `SET max_parallel_workers_per_gather = 0` để thấy ảnh hưởng của parallel query.
- `ALTER TABLE orders SET (autovacuum_vacuum_scale_factor = 0.02)` và giải thích khi nào cần.

## Definition of Done

Xong step khi **tất cả** các ô dưới đây đúng; chưa đúng thì chưa sang step sau.

- [ ] `./run.sh step 11` chạy hết, không lỗi.
- [ ] Mục 3: ước lượng `rows` sát thực tế hơn sau `CREATE STATISTICS`.
- [ ] Mục 5: thấy `external merge Disk` ở 64kB và `quicksort Memory` ở 64MB.
- [ ] Mục 6: keyset nhanh hơn OFFSET sâu rõ rệt; mục 9: `EXPLAIN` chỉ chạm vài partition.
- [ ] Mục 10: bảng phình sau UPDATE, VACUUM không trả đĩa, VACUUM FULL trả đĩa.
- [ ] Dùng `pg_stat_statements` tìm được câu tốn nhất và áp checklist 13 để giải thích.
