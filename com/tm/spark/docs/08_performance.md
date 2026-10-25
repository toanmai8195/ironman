# Step 08 — Performance và Spark UI

- **File:** `jobs/08_performance.py` · **Chạy:** job step 8 (thêm `-e HOLD=300 -p 4041:4040` khi `docker run`, rồi mở http://localhost:4041)
- **Mục đích:** biết các nút vặn chính và đọc Spark UI để tìm điểm nghẽn. Mọi phép đo bằng `timed()` (sink `noop`).
- **Docs:** https://spark.apache.org/docs/latest/sql-performance-tuning.html · https://spark.apache.org/docs/latest/web-ui.html

## Khái niệm mới

- **`spark.sql.shuffle.partitions`:** số partition sau mỗi shuffle (mặc định 200). Quá nhiều thì task bé, tốn overhead lịch; quá ít thì task to, tràn bộ nhớ.
- **Spill:** khi dữ liệu của một task không vừa bộ nhớ, Spark ghi tạm ra đĩa rồi đọc lại; chậm, hiện trong Spark UI ở cột *Spill*.
- **AQE (đã gặp ở step 04):** ở đây xem tác dụng `coalescePartitions`, gộp các partition nhỏ sau shuffle nên cấu hình 200 partition bớt tệ.
- **`cache()` / `persist(level)`:** lưu kết quả để dùng lại. Cache cũng *lazy*: action đầu tiên mới nạp. `StorageLevel` quyết định lưu ở đâu (`MEMORY_ONLY`, `MEMORY_AND_DISK`...). Phải `unpersist()` khi xong.
- **`repartition(n[, cols])` vs `coalesce(n)`:** `repartition` shuffle toàn bộ để chia lại (tăng/giảm, cân bằng, theo khoá); `coalesce` chỉ ghép partition kề nhau (không shuffle) và chỉ giảm được, có thể gây lệch.
- **Join hint / broadcast:** ép chiến lược join, xem step 04.
- **Khai báo `explain("formatted")`:** plan chia thành cây node đánh số kèm bảng chi tiết từng node, dễ đọc hơn bản mặc định.
- **Spark UI:** *Jobs/Stages* (thời gian từng task, shuffle read/write, spill), *SQL* (plan thật kèm số dòng mỗi node), *Storage* (dữ liệu đang cache), *Executors* (GC, bộ nhớ). Dấu hiệu skew: một task lâu hơn các task khác nhiều lần.
- **`HOLD`:** biến môi trường `-e HOLD=<giây>` của job giữ driver sống thêm N giây để kịp mở UI (`common.hold()`).

| # | Mục trong file | Làm gì | Quan sát |
|---|---|---|---|
| 1 | `spark.sql.shuffle.partitions` = 200 / 16 / 4 | Số partition sau shuffle | 200 task bé trên máy 4 core có overhead; ≈ 2-3× số core là hợp lý |
| 2 | AQE tắt / bật + `explain()` | Adaptive Query Execution | AQE gộp partition nhỏ sau shuffle, đổi chiến lược join, xử lý skew lúc chạy |
| 3 | `persist(MEMORY_AND_DISK)` và 4 lần chạy | Cache | Chỉ đáng khi dùng lại; nhớ `unpersist()`; xem tab Storage |
| 4 | `repartition(16)`, `repartition(16, "customer_id")`, `coalesce(2)` | Điều chỉnh số partition | `repartition` shuffle; `coalesce` chỉ giảm, không shuffle |
| 5 | Sort-merge vs `broadcast` join với `products` | So thời gian | Broadcast bỏ shuffle phía bảng lớn |
| 6 | Lọc `customers` trước khi join | Đẩy filter/chọn cột sớm | Catalyst thường tự làm, bạn vẫn nên viết rõ ý định |
| 7 | `explain("formatted")` | Plan dễ đọc theo node đánh số | |
| 8 | Checklist lỗi hay gặp | collect, UDF, shuffle partitions, skew, small files, tính lại | |

**Đọc Spark UI:** Jobs/Stages (task nào chậm, *Shuffle Read/Write*, *Spill*), SQL (plan thực tế kèm số dòng mỗi node), Storage (cache), Executors (GC time). Stage có một task chạy lâu gấp nhiều lần phần còn lại là dấu hiệu skew.

**Bài tập:** chạy lại mục 1 với `CORES=2` và `CORES=8`; thử bật `spark.sql.adaptive.coalescePartitions.enabled=false` ở mục 2.

## Definition of Done

Xong step khi **tất cả** các ô dưới đây đúng; chưa đúng thì chưa sang step sau.

- [ ] job step 8 chạy hết; chạy lại với `-e HOLD=300` và mở được Spark UI.
- [ ] Có bảng thời gian của mục 1 (200/16/4 partition) và bạn giải thích xu hướng.
- [ ] Mục 3: lần chạy có cache nhanh hơn, và thấy dữ liệu cache ở tab Storage trước khi `unpersist`.
- [ ] Tìm được trong Spark UI: một stage có shuffle read/write, tab SQL với số dòng mỗi node.
- [ ] Điền được checklist 8 điểm lỗi hiệu năng với ví dụ riêng của bạn cho ít nhất 3 điểm.
