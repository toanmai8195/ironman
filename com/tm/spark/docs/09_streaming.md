# Step 09 — Structured Streaming

- **File:** `jobs/09_streaming.py` · **Chạy:** job step 9 (cần step 1; mất khoảng 1 phút; ghi `/data/tmp/stream`)
- **Mục đích:** cùng API DataFrame nhưng trên dữ liệu vô hạn: cửa sổ thời gian, watermark, checkpoint, ghi idempotent.
- **Docs:** https://spark.apache.org/docs/latest/structured-streaming-programming-guide.html

## Khái niệm mới

- **Structured Streaming:** coi luồng dữ liệu như một bảng không ngừng tăng; bạn viết query DataFrame bình thường (`readStream`/`writeStream`), Spark chạy lặp lại trên phần dữ liệu mới.
- **Micro-batch:** mỗi lần chạy xử lý một lô dữ liệu mới; mỗi lô có `batchId`.
- **Source / Sink:** nguồn (`rate` sinh dữ liệu thử, `json`/`parquet` đọc thư mục, `kafka`), đích (`console`, `memory`, file, `foreachBatch`). Nguồn file bắt buộc khai báo schema.
- **Trigger:** khi nào chạy lô tiếp. `processingTime("5 seconds")` định kỳ; `availableNow=True` xử lý hết dữ liệu hiện có (chia nhiều lô nếu cần) rồi dừng, tiện cho job theo lịch. `maxFilesPerTrigger` giới hạn số file mỗi lô.
- **Output mode:** `append` (chỉ dòng mới, cố định), `update` (dòng có thay đổi), `complete` (toàn bộ bảng kết quả, chỉ cho aggregation).
- **Event time vs processing time:** event time là thời điểm sự kiện xảy ra (cột trong dữ liệu); processing time là lúc Spark xử lý. Tổng hợp theo thời gian nên dùng event time.
- **`window(col, "5 seconds")`:** gom theo cửa sổ thời gian; thêm tham số thứ ba để trượt (`window(ts, "10 seconds", "5 seconds")`).
- **State và Watermark:** aggregation streaming giữ *state* (kết quả dở dang mỗi cửa sổ). `withWatermark("ts", "10 seconds")` nói "dữ liệu trễ quá 10 giây so với event time lớn nhất thì bỏ", nhờ vậy Spark dọn được state cũ và aggregation `append` mới chạy được.
- **Checkpoint:** thư mục lưu offset đã xử lý và state; khởi động lại thì chạy tiếp đúng chỗ, không xử lý lặp. Đừng đổi logic aggregation khi dùng lại checkpoint cũ.
- **`foreachBatch(fn)`:** gọi hàm `fn(df, batch_id)` cho mỗi lô, bên trong dùng API batch (ghi parquet, ghi database...). Cùng `batch_id` có thể được gọi lại khi retry nên phải ghi idempotent.
- **Exactly-once:** nguồn phát lại được + checkpoint + sink idempotent (hoặc transactional) thì kết quả đúng một lần dù lỗi và retry.

| # | Mục trong file | Làm gì | Quan sát |
|---|---|---|---|
| 1 | `readStream.format("rate")` → `withWatermark` → `groupBy(window("timestamp","5 seconds"))` → console, `update` | Đếm theo cửa sổ 5s, in mỗi 5s trong 25s | Watermark 10s cho phép bỏ state cũ; cửa sổ cũ không đổi nữa |
| 2 | `readStream.json(events_raw)` + `maxFilesPerTrigger=1` + `trigger(availableNow=True)` + sink `memory` | Xử lý dần 4 file JSON thành 4 batch rồi dừng | Streaming bắt buộc khai báo schema; `complete` mode cho aggregate tích luỹ |
| 3 | `foreachBatch(write_batch)` + `checkpointLocation`, chạy 2 lần | Ghi parquet từng batch; lần 2 không xử lý lại file cũ | Checkpoint nhớ offset; `batch_id` dùng để ghi idempotent |
| 4 | Ghi chú | `append/update/complete`, watermark, checkpoint, exactly-once, Kafka | |

**Lưu ý:** đừng đổi logic aggregation khi dùng lại checkpoint cũ; xoá thư mục checkpoint nếu muốn chạy lại từ đầu.

**Bài tập:** đổi `rate` thành cửa sổ trượt `window(ts, "10 seconds", "5 seconds")`; thử `outputMode("append")` cho aggregate và đọc thông báo lỗi; thay file source bằng Kafka (stack Kafka ở `com/tm/docker/ironman`).

## Definition of Done

Xong step khi **tất cả** các ô dưới đây đúng; chưa đúng thì chưa sang step sau.

- [ ] job step 9 chạy hết, không lỗi.
- [ ] Mục 1: thấy các cửa sổ 5s in ra theo batch trong console.
- [ ] Mục 2: số batch bằng số file JSON (4) nhờ `maxFilesPerTrigger=1`.
- [ ] Mục 3: lần chạy 2 không có batch nào, và bạn giải thích bằng checkpoint.
- [ ] Nói được output mode nào hợp với aggregation, và watermark dọn state thế nào.
