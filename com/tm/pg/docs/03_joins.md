# Step 03 — JOIN

- **File:** `sql/03_joins.sql` · **Chạy:** `./run.sh step 3` (chỉ đọc)
- **Mục đích:** nắm từng loại join qua câu hỏi thật của Ironshop, và các bẫy kinh điển (LEFT thành INNER, NOT IN với NULL, fan-out).
- **Docs:** https://www.postgresql.org/docs/current/queries-table-expressions.html

## Các query

| # | Loại | Query | Dùng để làm gì | Quan sát |
|---|---|---|---|---|
| 1 | INNER | order_items ⨝ products ⨝ categories | Doanh thu theo danh mục | Chỉ dòng khớp cả hai phía |
| 2 | LEFT | customers ⟕ orders `WHERE o.id IS NULL` | Khách chưa mua gì (anti-join kiểu LEFT) | ~2.500 khách |
| 2b | LEFT (bẫy) | điều kiện `o.status` ở `WHERE` vs ở `ON` | Điều kiện của bảng phải trong ON, nếu không LEFT JOIN thành INNER | Hai con số khác nhau hẳn |
| 3 | RIGHT | order_items ⟖ products | Sản phẩm chưa bán được cái nào | Là LEFT đảo vế; ít dùng |
| 4 | FULL | hai `VALUES` `USING (id)` | Đối soát hai nguồn: cái chỉ có ở A, chỉ có ở B, có ở cả hai | id 1 và 4 có phía NULL |
| 5 | CROSS | tier × `enum_range(order_status)` rồi LEFT JOIN | Lưới báo cáo đủ ô kể cả ô 0 | `count(o.id)` đếm đúng ô trống = 0 |
| 6 | SELF | categories child ⟕ parent | Tên cha của từng danh mục | Gốc có parent NULL |
| 7 | LATERAL | `CROSS JOIN LATERAL (... LIMIT 3)` | Top-3 sản phẩm đắt nhất mỗi danh mục | Subquery chạy một lần mỗi dòng bên trái |
| 8 | Semi-join | `WHERE EXISTS (...)` | Khách từng có đơn bị huỷ | Không nhân dòng như JOIN |
| 9 | Anti-join | `NOT EXISTS` vs `NOT IN (... NULL)` | `NOT IN` gặp một NULL thì kết quả rỗng | Luôn dùng `NOT EXISTS` |
| 10 | Fan-out | `SUM(o.total)` sau JOIN order_items | Join 1-N làm cột bên "1" bị nhân lên | Con số sai gấp ~2,5 lần |
| 11 | EXPLAIN | orders ⨝ customers, `c.id < 100` | Xem planner chọn Nested Loop / Hash | Đọc kỹ ở step 11 |

## Bài tập

- Viết lại query 2 bằng `NOT EXISTS` và `NOT IN`; so sánh `EXPLAIN` (Hash Anti Join).
- Tổng doanh thu mỗi khách kèm số item: tính ở hai cấp (subquery) để tránh fan-out.
- `JOIN ... USING (col)` khác `ON a.col = b.col` ở đâu (cột kết quả chỉ xuất hiện một lần)?

## Definition of Done

Xong step khi **tất cả** các ô dưới đây đúng; chưa đúng thì chưa sang step sau.

- [ ] `./run.sh step 3` chạy hết, không lỗi.
- [ ] Mục 2b: hai con số khác nhau và bạn giải thích vì sao đặt điều kiện ở `WHERE` làm LEFT thành INNER.
- [ ] Mục 9: `NOT EXISTS` đúng, `NOT IN` ra 0, và bạn giải thích do NULL.
- [ ] Mục 10: thấy tổng sai do fan-out và viết được cách tính đúng.
- [ ] Viết lại anti-join bằng `NOT EXISTS` và `NOT IN`, so `EXPLAIN` (bài tập).
