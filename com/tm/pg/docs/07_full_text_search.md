# Step 07 — Full Text Search

- **File:** `sql/07_full_text_search.sql` · **Chạy:** `./run.sh step 7` (thêm cột `products.tsv`, 2 sản phẩm tiếng Việt)
- **Mục đích:** làm ô tìm kiếm sản phẩm: chuẩn hoá văn bản, xếp hạng, highlight, tìm gần đúng.
- **Docs:** https://www.postgresql.org/docs/current/textsearch.html · https://www.postgresql.org/docs/current/pgtrgm.html · https://www.postgresql.org/docs/current/unaccent.html

Khái niệm: `tsvector` = văn bản đã tách token, stem, bỏ stopword, kèm vị trí. `tsquery` = biểu thức tìm. Toán tử khớp: `@@`.

## Các query

| # | Query | Dùng để làm gì | Quan sát |
|---|---|---|---|
| 1 | `to_tsvector`, `to_tsquery`, `plainto_`, `phraseto_`, `websearch_to_tsquery` | Hiểu 4 cách tạo query | `websearch_to_tsquery` nhận cú pháp kiểu Google (`"cụm từ"`, `-loại trừ`, `or`), an toàn với input người dùng |
| 1b | cấu hình `'english'` vs `'simple'` | Stem/stopword so với không xử lý gì | `jumping`→`jump`; `simple` giữ nguyên |
| 2 | `description ILIKE '%battery%'` | Baseline | Seq Scan, không xếp hạng, không stem |
| 3 | Cột `tsv GENERATED ALWAYS AS (setweight(...A) \|\| setweight(...B)) STORED` + `GIN` | Tự cập nhật vector có trọng số (tên quan trọng hơn mô tả) | Query `@@` chuyển sang Bitmap Index Scan |
| 4 | `ts_rank` / `ts_rank_cd` | Sắp xếp theo độ liên quan | `rank_cd` tính cả độ gần nhau của từ |
| 5 | `ts_headline` | Đoạn trích có đánh dấu `<b>` từ khớp | Tốn CPU, chỉ gọi cho trang kết quả đang hiển thị |
| 6 | 4 `count(*) FILTER` với `battery life`, `"long battery life"`, `battery -fast`, `sturdy or modern` | So AND, cụm từ, loại trừ, OR | |
| 7 | `to_tsquery('head:*')` | Tìm theo prefix | Khớp `headphones` |
| 8 | `ts_debug` | Xem từng token đi qua từ điển nào | Dùng để gỡ lỗi khi không khớp như mong đợi |
| 9 | `unaccent` + cấu hình `simple` | Tìm tiếng Việt không dấu ("dien thoai" ra "Điện thoại") | Postgres không có stemmer tiếng Việt; dùng `simple` + `unaccent` |
| 10 | `pg_trgm`: `show_trgm`, `similarity`, `% `, `gin_trgm_ops` | `ILIKE '%phone%'` dùng được index; gõ sai "wirless hedphones" vẫn ra | FTS khớp theo từ, trigram khớp theo ký tự |
| 11 | JOIN categories + `ts_rank` + lọc giá + `LIMIT` | Truy vấn tìm kiếm thực tế: FTS kết hợp bộ lọc quan hệ | |

## Bài tập

- Thêm `category.name` vào `tsv` (cần trigger vì generated column không đọc được bảng khác).
- Đo `EXPLAIN ANALYZE` với từ rất phổ biến ("product") và từ hiếm ("ergonomic") để thấy chi phí tăng theo số kết quả.
- Gộp tìm chính xác (FTS) và tìm mờ (trigram) bằng `UNION` khi FTS không ra kết quả.

## Definition of Done

Xong step khi **tất cả** các ô dưới đây đúng; chưa đúng thì chưa sang step sau.

- [ ] `./run.sh step 7` chạy hết, không lỗi.
- [ ] Mục 1: giải thích `to_tsvector('english', ...)` đã stem và bỏ stopword khác `simple` ra sao.
- [ ] Mục 3: query FTS dùng GIN (`Bitmap Index Scan on idx_products_tsv`) thay vì Seq Scan của `ILIKE`.
- [ ] Mục 9: "dien thoai" tìm ra "Điện thoại"; mục 10: gõ sai "wirless hedphones" vẫn ra kết quả.
- [ ] Phân biệt được khi nào dùng FTS và khi nào dùng `pg_trgm`.
