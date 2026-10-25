# Step 03 — Aggregation

- **File:** `jobs/03_aggregations.py` · **Chạy:** job step 3 (cần step 1, 2; chỉ đọc)
- **Mục đích:** tổng hợp doanh thu, hành vi; hiểu chi phí của distinct, pivot, rollup.
- **Docs:** https://spark.apache.org/docs/latest/sql-ref-functions-builtin.html#aggregate-functions

## Khái niệm mới

- **`groupBy(...).agg(...)`:** `groupBy` trả về `GroupedData` (chưa phải DataFrame); `agg` mới tính các hàm tổng hợp (`sum`, `count`, `avg`, `min`, `max`...), có thể nhiều hàm một lúc và đặt tên bằng `alias`.
- **Aggregate hai pha:** Spark gom cục bộ từng partition (*partial*) rồi mới shuffle và gom lần cuối (*final*), nên shuffle chỉ mang dữ liệu đã thu gọn. Thấy trong plan là `HashAggregate` – `Exchange` – `HashAggregate`.
- **`countDistinct` vs `approx_count_distinct`:** đếm chính xác phải giữ mọi giá trị khác nhau (tốn bộ nhớ, shuffle nặng); bản xấp xỉ dùng thuật toán HyperLogLog++ với sai số cấu hình được (`rsd`), rẻ hơn nhiều.
- **`percentile_approx`:** phân vị xấp xỉ, đủ cho P50/P90/P99, không cần sắp xếp toàn bộ.
- **`collect_list` / `collect_set`:** gom giá trị của nhóm thành mảng trong một dòng; toàn bộ mảng phải nằm gọn trong bộ nhớ một task nên cẩn thận với nhóm lớn.
- **`pivot`:** xoay giá trị của một cột thành nhiều cột. Truyền sẵn danh sách giá trị, nếu không Spark phải chạy thêm một job để tìm.
- **`rollup` / `cube` / `grouping_id`:** tổng hợp kèm subtotal và grand total; `rollup(a,b)` cho (a,b), (a), (); `cube` cho mọi tổ hợp. Ô NULL là dòng tổng hợp, `grouping_id` giúp phân biệt với NULL thật.
- **`timed()` (helper của dự án):** chạy DataFrame bằng sink `noop` để đo thời gian mà không ghi ra đâu và không bị optimizer cắt bỏ.

| # | Mục trong file | Làm gì | Quan sát |
|---|---|---|---|
| 1 | `groupBy(date_trunc("month")).agg(count, sum, avg, countDistinct)` | Doanh thu theo tháng (chưa huỷ), tổng đơn từ `order_items` | Tính `total` mỗi đơn rồi join ngược |
| 2 | `sum(when(...))`, `avg(cond.cast("int"))` | Aggregate có điều kiện, tỉ lệ đơn lớn | Tương đương `FILTER`/`CASE` trong SQL |
| 3 | `countDistinct` vs `approx_count_distinct` + `timed()` | Distinct chính xác vs HyperLogLog++ | Xấp xỉ rẻ hơn; sai số ~2% theo tham số `rsd` |
| 4 | `percentile_approx([0.5,0.9,0.99])`, `collect_set` | Phân vị, gom tập giá trị | `collect_*` dồn vào bộ nhớ một dòng, cẩn thận với nhóm lớn |
| 5 | `pivot("status", values)` | Bảng chéo trạng thái × tháng | Truyền sẵn danh sách giá trị để Spark khỏi chạy thêm một job tìm giá trị |
| 6 | `rollup("category", "brand")` + `grouping_id()` | Subtotal và grand total | Dòng NULL là dòng tổng hợp; `cube` cho mọi tổ hợp |
| 7 | Funnel theo `device`: view → click → cart → purchase | Tỉ lệ chuyển đổi từ clickstream | |
| 8 | `explain()` của `groupBy().count()` | HashAggregate hai pha | partial aggregate → `Exchange` → final: giảm dữ liệu trước khi shuffle |

**Bài tập:** tính funnel theo *người dùng* (một user có ít nhất một purchase / ít nhất một view). Thử `cube` thay `rollup`.

## Definition of Done

Xong step khi **tất cả** các ô dưới đây đúng; chưa đúng thì chưa sang step sau.

- [ ] job step 3 chạy hết, không lỗi.
- [ ] Mục 3: số `approx` lệch `exact` trong khoảng vài %, và bạn nêu được vì sao nó rẻ hơn.
- [ ] Chỉ ra `HashAggregate` hai pha và `Exchange` ở mục 8, giải thích vì sao partial aggregate giảm dữ liệu shuffle.
- [ ] Đọc được dòng subtotal/grand total trong output `rollup` bằng `grouping_id`.
- [ ] Làm bài tập funnel theo người dùng.
