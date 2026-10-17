# Báo cáo tổng: Mongo và StarRocks cho bài toán segmentation

Report từng test: [test1-tag-rows-vs-agg.md](test1-tag-rows-vs-agg.md), [test2-tag-agg-vs-sr.md](test2-tag-agg-vs-sr.md), [test3-segment.md](test3-segment.md), [test4-getall.md](test4-getall.md). Số liệu thô: `report/limited/` và `report/unlimited/`.

## Kịch bản chung

- Gold: 50 tag, 10 attribute, universe 50 triệu user, mỗi tag 5 đến 10 triệu user, cùng bảng gold cho mọi test.
- Segment: 300 segment, mỗi segment là and/or/not của 10 tag bất kỳ (seed 42), kết quả 5 đến 10 triệu user; cùng các segment cho Mongo và StarRocks.
- Mongo: bitmap lưu thành chunk tối đa 8MB, tối đa 10 chunk đọc hoặc ghi đồng thời. StarRocks: bitmap native.
- Hai chế độ: có giới hạn (StarRocks 6 CPU/8GB, Mongo 3 CPU/6GB, service 2 CPU/3GB) và không giới hạn.

## Latency p50 (ms)

| Test | Case | có giới hạn | không giới hạn |
|---|---|---|---|
| 1 | t1-rows: gold → rows → bitmap → Mongo | 1,692 | 1,692 |
| 1 | t1-agg: gold → agg → bitmap → Mongo | 233.2 | 172.4 |
| 2 | t2-agg: gold → agg → bitmap → Mongo | 258.8 | 212.3 |
| 2 | t2-sr: gold → bitmap trong StarRocks | 279.1 | 209.9 |
| 3 | t3-mongo: tag Mongo → segment Mongo | 179.5 | 154.4 |
| 3 | t3-sr: tag StarRocks → segment StarRocks | 104.6 | 105.0 |
| 4 | t4-mongo: segment Mongo → service | 46.9 | 39.5 |
| 4 | t4-sr: segment StarRocks → service | 1,378 | 1,408 |

## Latency p90 (ms)

| Test | Case | có giới hạn | không giới hạn |
|---|---|---|---|
| 1 | t1-rows: gold → rows → bitmap → Mongo | 2,133 | 2,137 |
| 1 | t1-agg: gold → agg → bitmap → Mongo | 267.1 | 217.6 |
| 2 | t2-agg: gold → agg → bitmap → Mongo | 306.4 | 271.2 |
| 2 | t2-sr: gold → bitmap trong StarRocks | 351.0 | 280.0 |
| 3 | t3-mongo: tag Mongo → segment Mongo | 210.1 | 185.2 |
| 3 | t3-sr: tag StarRocks → segment StarRocks | 126.3 | 123.7 |
| 4 | t4-mongo: segment Mongo → service | 53.4 | 45.0 |
| 4 | t4-sr: segment StarRocks → service | 1,611 | 1,657 |

## Latency p99 (ms)

| Test | Case | có giới hạn | không giới hạn |
|---|---|---|---|
| 1 | t1-rows: gold → rows → bitmap → Mongo | 2,214 | 2,317 |
| 1 | t1-agg: gold → agg → bitmap → Mongo | 384.7 | 311.7 |
| 2 | t2-agg: gold → agg → bitmap → Mongo | 517.8 | 393.9 |
| 2 | t2-sr: gold → bitmap trong StarRocks | 594.5 | 436.7 |
| 3 | t3-mongo: tag Mongo → segment Mongo | 242.6 | 237.8 |
| 3 | t3-sr: tag StarRocks → segment StarRocks | 196.3 | 208.0 |
| 4 | t4-mongo: segment Mongo → service | 84.9 | 77.2 |
| 4 | t4-sr: segment StarRocks → service | 1,753 | 1,798 |

## Latency avg (ms)

| Test | Case | có giới hạn | không giới hạn |
|---|---|---|---|
| 1 | t1-rows: gold → rows → bitmap → Mongo | 1,724 | 1,732 |
| 1 | t1-agg: gold → agg → bitmap → Mongo | 230.7 | 176.8 |
| 2 | t2-agg: gold → agg → bitmap → Mongo | 264.4 | 221.4 |
| 2 | t2-sr: gold → bitmap trong StarRocks | 284.8 | 224.2 |
| 3 | t3-mongo: tag Mongo → segment Mongo | 183.3 | 158.9 |
| 3 | t3-sr: tag StarRocks → segment StarRocks | 108.9 | 109.5 |
| 4 | t4-mongo: segment Mongo → service | 46.9 | 40.4 |
| 4 | t4-sr: segment StarRocks → service | 1,379 | 1,408 |

## Network mỗi lần đo và tài nguyên (có giới hạn)

| Test | Case | service rx mỗi lần (MB) | service tx mỗi lần (MB) | CPU service avg (core) | CPU StarRocks avg | CPU Mongo avg | RAM max StarRocks (GB) |
|---|---|---|---|---|---|---|---|
| 1 | t1-rows | 95.8 | 6.2 | 1.00 | 0.94 | 0.07 | 3.2 |
| 1 | t1-agg | 7.9 | 5.9 | 0.21 | 3.09 | 0.07 | 3.4 |
| 2 | t2-agg | 6.9 | 5.1 | 0.18 | 3.98 | 0.21 | 3.6 |
| 2 | t2-sr | 0.0 | 0.0 | 0.03 | 3.40 | 0.06 | 3.3 |
| 3 | t3-mongo | 62.7 | 6.3 | 1.02 | 0.06 | 0.41 | 2.8 |
| 3 | t3-sr | 0.0 | 0.0 | 0.03 | 1.37 | 0.06 | 4.8 |
| 4 | t4-mongo | 2.8 | 0.0 | 1.14 | 0.66 | 0.07 | 3.4 |
| 4 | t4-sr | 92.2 | 0.1 | 1.01 | 0.85 | 0.06 | 3.4 |

## Kết luận và khuyến nghị cho bài toán segmentation

### Kết quả từng test (p50, ms; có giới hạn / không giới hạn)

| Test | Mongo | StarRocks | Nhận xét |
|---|---|---|---|
| 1. Tag: gold → rows so với gold → agg (cùng lưu Mongo) | rows 1692 / 1692, agg 233 / 172 | | agg nhanh hơn rows khoảng 7 đến 10 lần; rows kéo khoảng 96MB mỗi tag về service, agg chỉ khoảng 8MB |
| 2. Tag: gold → agg → Mongo so với gold → bitmap StarRocks | 259 / 212 | 279 / 210 | gần ngang nhau (chênh dưới 10%); StarRocks không có network ra service |
| 3. Segment từ tag trong Mongo so với trong StarRocks | 180 / 154 | 105 / 105 | StarRocks nhanh hơn 1,5 đến 1,7 lần; Mongo kéo khoảng 63MB mỗi segment về service |
| 4. Lấy toàn bộ user của segment | 47 / 40 | 1378 / 1408 | Mongo nhanh hơn khoảng 29 đến 36 lần; StarRocks kéo khoảng 92MB mỗi lần (từng hàng) |

p99 (có giới hạn): test 3 Mongo 243ms, StarRocks 196ms; test 4 Mongo 85ms, StarRocks 1753ms.

### Điều rút ra từ số liệu

1. **Không dùng gold → rows.** Chậm hơn agg 7 đến 10 lần ở bước tag, tốn network gấp khoảng 12 lần, và không có lợi gì thêm (bitmap kết quả như nhau).
2. **Tạo bitmap tag: Mongo agg và StarRocks ngang nhau** (cùng quét gold trong StarRocks; phần còn lại là ghi vào Mongo khoảng 20 đến 30ms hoặc ghi vào bảng bitmap của StarRocks). Hai bên khác nhau không đáng kể so với nhiễu giữa các lần chạy, nên chọn theo nơi cần dữ liệu ở bước sau.
3. **Tính segment: StarRocks thắng.** Nó tính tại chỗ, không có network ra service (service gần như nhàn rỗi, 0,03 core). Mongo phải kéo 10 tag (khoảng 63MB) về service; trong 180ms của mỗi segment thì tải chunk chỉ khoảng 19ms, còn **giải mã và and/or/not khoảng 123ms là việc CPU trong service** (1 core). Vì thế bỏ giới hạn tài nguyên cũng chỉ cải thiện 180ms xuống 154ms. Khi cần tính nhiều segment cùng lúc, Mongo sẽ cần thêm nhiều CPU service và băng thông, còn StarRocks mở rộng bằng CPU của chính nó (khoảng 1,4 core ở nhịp 4,6 segment/giây).
4. **Lấy toàn bộ user: Mongo thắng rõ.** Mongo trả một blob khoảng 6,3MB rồi service duyệt trong bộ nhớ; StarRocks trả từng user dạng hàng qua giao thức MySQL (khoảng 92MB mỗi lần). Lưu ý: docker stats ghi service chỉ nhận khoảng 2,8MB mỗi lần ở Mongo, thấp hơn 6,3MB của blob vì case này chỉ chạy khoảng 2 giây nên thiếu mẫu; con số 6,3MB là theo kích thước blob.
5. **Giới hạn tài nguyên (StarRocks 6 CPU, Mongo 3 CPU, service 2 CPU) chỉ làm chậm bước tag** (khoảng 20 đến 26%); test 3 và 4 gần như không đổi, nên giới hạn đó đủ cho segment và đọc.

### Khuyến nghị: dùng StarRocks để tính, dùng Mongo để phục vụ

- **Tag:** gold → `bitmap_agg` trong StarRocks, giữ bitmap tag trong StarRocks (bảng bitmap). Chi phí tương đương lưu Mongo, và mở đường cho bước sau.
- **Tạo segment:** tính trong StarRocks (and/or/not trên bitmap native). Nhanh hơn, không tốn băng thông, không tốn CPU service.
- **Phục vụ và xuất toàn bộ user của segment:** sao chép bitmap segment kết quả từ StarRocks sang Mongo (chunk tối đa 8MB) cho các consumer cần lấy danh sách user, vì Mongo nhanh hơn khoảng 30 lần ở p50. Nếu việc lấy toàn bộ user hiếm, có thể đọc thẳng từ StarRocks và chấp nhận khoảng 1,4 giây mỗi lần.
- **Không nên** chạy toàn bộ trong service với Mongo (kéo tag về service để tính): chậm hơn StarRocks ở bước segment, và tốn khoảng 63MB network, khoảng 1 core service cho mỗi segment.

Cách làm thay thế đơn giản hơn nếu muốn chỉ có một kho: Mongo agg cho tag, tính segment trong service. Cách này chạy được (180ms mỗi segment) nhưng phụ thuộc vào CPU và băng thông của service khi tăng tải.

### Giới hạn của kết luận này

- Bước "sao chép segment từ StarRocks sang Mongo" **chưa được đo** trong lượt này. Ước lượng chi phí của nó gần với bước tag agg (một bitmap 6MB đi qua `bitmap_to_base64`, giải mã, ghi chunk), nhưng đó chỉ là ước lượng; cần một test riêng (test 5) trước khi chốt kiến trúc này.
- Mọi bitmap tag và segment đều khoảng 6,3MB, nhỏ hơn 8MB, nên mỗi bitmap chỉ là một chunk; giới hạn 10 chunk đồng thời thực tế là 10 tag đọc song song. Nếu universe lớn hơn (bitmap vượt 8MB) cách chia chunk mới có tác dụng và kết quả của Mongo có thể khác.
- Mỗi case chạy một lần cho mỗi chế độ, nên chênh lệch dưới khoảng 15% có thể là nhiễu (xem phần so sánh có giới hạn và không giới hạn trong từng test). CPU, RAM và network đo bằng `docker stats` mỗi 1 đến 2 giây, thô với case ngắn (test 1 agg, test 2 chỉ khoảng 10 đến 20 giây).
- Compute của StarRocks (test 3) là cả câu SQL gồm tính và ghi; Mongo gồm tải, giải mã, tính, serialize và ghi. Bước `DELETE` segment cũ của StarRocks không nằm trong thời gian đo.
- Kịch bản là segment 5 đến 10 triệu user trên universe 50 triệu; kết quả có thể khác với segment rất nhỏ hoặc rất lớn.

