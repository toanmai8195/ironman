# Step 04 — Join và data skew

- **File:** `jobs/04_joins.py` · **Chạy:** `./run.sh step 4` (cần step 1; chỉ đọc)
- **Mục đích:** join là phép tốn kém nhất trong Spark. Biết chọn chiến lược join và xử lý skew.
- **Docs:** https://spark.apache.org/docs/latest/sql-performance-tuning.html#join-strategy-hints-for-sql-queries · https://spark.apache.org/docs/latest/sql-performance-tuning.html#optimizing-skew-join

## Khái niệm mới

- **Các kiểu join:** `inner`, `left`, `right`, `full` như SQL; `left_semi` (giữ dòng trái có khớp, không thêm cột phải); `left_anti` (giữ dòng trái *không* khớp); `crossJoin` (tích Descartes, dễ nổ số dòng).
- **Sort-merge join:** mặc định khi cả hai bảng lớn. Shuffle cả hai phía theo khoá, sắp xếp rồi trộn. Plan: `Exchange` + `Sort` + `SortMergeJoin`.
- **Broadcast hash join:** bảng nhỏ được gửi tới mọi executor, bảng lớn đứng yên, không shuffle. Spark tự chọn nếu bảng nhỏ hơn `spark.sql.autoBroadcastJoinThreshold` (mặc định 10MB), hoặc ép bằng `F.broadcast(df)` (hint).
- **Data skew:** khoá phân bố lệch (vd khách 1 có 5% đơn) khiến một partition ôm quá nhiều dòng; cả stage phải chờ task chậm nhất.
- **`spark_partition_id()`:** trả về id partition của từng dòng; groupBy trên đó để thấy phân bố dòng theo partition.
- **Salting:** thêm số ngẫu nhiên `0..N-1` vào khoá của bảng lớn và nhân bảng nhỏ lên N bản để khoá nóng được rải ra N partition.
- **AQE (Adaptive Query Execution):** Spark 3 điều chỉnh plan *lúc chạy* dựa vào kích thước thật sau shuffle: gộp partition nhỏ, đổi sang broadcast, tách partition lệch (`skewJoin`). Bật mặc định từ Spark 3.2.
- **Cột trùng tên:** join theo biểu thức giữ cả hai cột `customer_id`, gây lỗi mơ hồ khi chọn; join theo tên cột (`"customer_id"`) chỉ giữ một.

| # | Mục trong file | Làm gì | Quan sát |
|---|---|---|---|
| 1 | `inner, left, right, full, left_semi, left_anti, crossJoin` | Đếm kết quả mỗi loại | right giữ khách chưa mua; anti = khách chưa mua; semi = có ít nhất một đơn |
| 2 | Join theo biểu thức vs theo tên cột | Bẫy cột trùng tên | Theo tên cột (`"customer_id"`) chỉ giữ một cột |
| 3 | Sort-merge join `explain()` | Cả hai phía `Exchange` + `Sort` | Dùng khi hai bảng đều lớn |
| 4 | `F.broadcast(small)` `explain()` | Broadcast hash join | Bảng lớn không shuffle; ngưỡng tự động `autoBroadcastJoinThreshold` (10MB) |
| 5 | `spark_partition_id()` + `groupBy` | Đo skew: dòng mỗi partition sau join | Một partition lớn vượt trội do khách 1 |
| 6 | **Salting:** thêm `salt` ngẫu nhiên 0..7 vào bảng lớn, nhân bảng nhỏ lên 8 lần | Rải khoá nóng ra nhiều partition | Phân bố đều hơn; tốn thêm dữ liệu bảng nhỏ |
| 7 | **AQE skew join** (`adaptive.skewJoin.enabled`) | Spark tự tách partition lệch lúc chạy | Cách ít sửa code nhất; xem Spark UI > SQL |
| 8 | **Tách khoá nóng:** broadcast phần nóng, join thường phần còn lại, `unionByName` | Xử lý riêng hot key | Phù hợp khi biết trước vài khoá nóng |

**Bài tập:** đổi `N` salt thành 32 và đo lại phân bố; thử `hint("shuffle_hash")` và `hint("merge")` rồi `explain()`.

## Definition of Done

Xong step khi **tất cả** các ô dưới đây đúng; chưa đúng thì chưa sang step sau.

- [ ] `./run.sh step 4` chạy hết, không lỗi.
- [ ] Mục 3 và 4: chỉ ra `SortMergeJoin` (có Exchange hai phía) và `BroadcastHashJoin` (không Exchange phía bảng lớn).
- [ ] Mục 5: nhìn thấy một partition ôm nhiều dòng vượt trội; mục 6 và 7: phân bố đều hơn rõ rệt.
- [ ] Nói được 3 cách xử lý skew, ưu và nhược của từng cách.
- [ ] Làm bài tập đổi số salt và thử hint `shuffle_hash`, `merge`.
