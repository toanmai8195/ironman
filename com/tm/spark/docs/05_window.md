# Step 05 — Window function

- **File:** `jobs/05_window.py` · **Chạy:** job step 5 (cần step 1, 2; chỉ đọc)
- **Mục đích:** xếp hạng, so với kỳ trước, cộng dồn và sessionization (gom event thành phiên) mà không cần self join.
- **Docs:** https://spark.apache.org/docs/latest/sql-ref-syntax-qry-select-window.html

## Khái niệm mới

- **Window function:** tính một giá trị cho *từng dòng* dựa trên nhóm dòng lân cận, khác `groupBy` là không gộp dòng. Dùng `F.func().over(window_spec)`.
- **Window spec:** `Window.partitionBy(...)` chia nhóm, `.orderBy(...)` sắp xếp trong nhóm, `.rowsBetween(a, b)` / `.rangeBetween(a, b)` chọn khung dòng.
- **Frame `rows` vs `range`:** `rowsBetween(-2, 0)` là 2 dòng trước đến dòng hiện tại; `rangeBetween` tính theo *giá trị* của cột sắp xếp (vd 6 ngày trước). `Window.unboundedPreceding` và `Window.currentRow` là hai mốc đặc biệt.
- **Hàm xếp hạng:** `row_number` (1,2,3 duy nhất), `rank` (đồng hạng, nhảy số), `dense_rank` (đồng hạng, không nhảy).
- **Hàm so sánh dòng:** `lag(col, n)` giá trị n dòng trước, `lead` n dòng sau; dùng cho tăng trưởng so kỳ trước.
- **Window không có `partitionBy`:** toàn bộ dữ liệu đổ về một partition; ổn với vài chục dòng, thảm hoạ với dữ liệu lớn (Spark sẽ cảnh báo).
- **Chi phí:** window luôn kèm `Exchange` theo khoá partition và `Sort` theo khoá order.
- **Sessionization:** gom chuỗi event thành phiên: đánh cờ 1 khi khoảng cách tới event trước vượt ngưỡng, rồi `sum(cờ)` cộng dồn trong window thành `session_id`.

| # | Mục trong file | Làm gì | Quan sát |
|---|---|---|---|
| 1 | `row_number / rank / dense_rank` trên `Window.partitionBy("category").orderBy(desc("revenue"))` | Top 3 sản phẩm theo doanh thu mỗi danh mục | Lọc `rn <= 3` sau khi tính |
| 2 | `lag`, `sum().over(rowsBetween(unboundedPreceding, currentRow))`, `avg().over(rowsBetween(-2, 0))` | % tăng so với tháng trước, cộng dồn, trung bình trượt 3 tháng | Window không có `partitionBy` kéo cả dữ liệu về 1 partition (cảnh báo khi dữ liệu lớn) |
| 3 | `rangeBetween(-6*86400, 0)` | Đơn trong 7 ngày gần nhất theo giá trị thời gian | `rows` đếm dòng, `range` theo giá trị cột sắp xếp |
| 4 | Top-N mỗi `tier` | Khách mua nhiều nhất mỗi tier | |
| 5 | **Sessionization:** `lag(ts)` → cờ `new_session` khi gap > ngưỡng → `sum(cờ).over(w)` | Gán `session_id` cho event của từng user | Kỹ thuật kinh điển; ngưỡng 7 ngày vì dữ liệu thưa |
| 6 | `explain()` | `Exchange` theo `partitionBy` + `Sort` theo `orderBy` | Window luôn kèm shuffle + sort |

**Bài tập:** đổi gap thành 1 ngày và xem số phiên; tính thời lượng và số event mỗi phiên; tìm sản phẩm xem nhiều nhất trước lần `purchase` đầu tiên của mỗi phiên.

## Definition of Done

Xong step khi **tất cả** các ô dưới đây đúng; chưa đúng thì chưa sang step sau.

- [ ] job step 5 chạy hết, không lỗi.
- [ ] Mục 1: giải thích được vì sao `rank` và `row_number` ra khác nhau khi đồng hạng.
- [ ] Mục 2: tự kiểm tay một tháng: `mom_pct`, `running`, `ma3` đúng với số liệu gốc.
- [ ] Mục 5: giải thích 3 bước của sessionization (lag, cờ, cộng dồn) và đổi ngưỡng gap để thấy số phiên đổi.
- [ ] Chỉ ra `Exchange` + `Sort` trong plan window.
