# Báo cáo benchmark bitmap: Mongo vs StarRocks

## Kịch bản

- Gold: 30 tag, 6 attribute, universe 50 triệu user. Mỗi tag 5.00 đến 10.00 triệu user (trung bình 7.55 triệu).
- Segment: 300 segment, mỗi segment là biểu thức AND/OR/AND NOT trên 10 tag ngẫu nhiên (seed 42), kết quả 5.27 đến 9.72 triệu user. Cùng các segment cho mọi pipeline.
- Lấy toàn bộ user: 40 segment mẫu ngẫu nhiên (cùng mẫu cho Mongo và StarRocks). Tổng user đọc được: Mongo 303,328,588, StarRocks 303,328,588, khớp nhau.
- Mỗi lúc chỉ xử lý một tag (bài 1) hoặc một segment (bài 2); tạo xong cả 30 tag mới sang segment. Mongo tối đa 10 lần get đồng thời (mỗi blob nhỏ hơn 1 chunk 8MB).
- Mỗi bước chạy một lần trong container service riêng; thứ tự: nhóm 1 (1.1, 1.2), nhóm 2 (1.2, 2.1, 3.1), nhóm 3 (1.3, 2.2, 3.2); xoá hết data giữa các nhóm.
- Thời gian đo bằng benchmark (avg, p50, p90, p99, ms). CPU (core), RAM và network lấy từ `docker stats` lấy mẫu trong từng bước.

- **limited**: Có giới hạn (SR 6 CPU/8GB, Mongo 3 CPU/6GB, service 2 CPU/3GB)
- **unlimited**: Không giới hạn (SR, Mongo, service dùng tối đa 10 core, RAM không giới hạn)

- Kích thước bitmap roaring lưu trong Mongo: tag 6.3MB và segment 6.3MB (log chỉ ghi 1 chữ số thập phân; mọi blob đều bằng nhau ở mức này). Tag và segment 5 đến 10 triệu user trên universe 50 triệu đủ dày để roaring dùng bitmap container, nên mọi blob đều gần bằng kích thước tối đa của universe (50 triệu bit, khoảng 6,3MB).

## Kết luận nhanh (p50, ms; số có giới hạn / không giới hạn)

- Bài 1: Mongo rows 1,705 / 1,717, Mongo agg 261.0 / 197.7, StarRocks 268.3 / 214.0. Mongo rows chậm hơn khoảng 6.5 lần so với agg vì phải kéo từng user về service; StarRocks và Mongo agg gần ngang nhau.
- Bài 2: Mongo 101.1 / 90.6, StarRocks 104.0 / 103.9. Hai bên gần ngang nhau; StarRocks ít biến động hơn ở p90 khi có giới hạn. Mongo phải tải khoảng 61MB mỗi segment, StarRocks gần như không có network ra service.
- Bài 3: Mongo 40.7 / 38.9, StarRocks 1,388 / 1,392. Mongo nhanh hơn khoảng 34 lần: Mongo trả một blob nén khoảng 3.3MB, còn StarRocks trả từng user dạng hàng, khoảng 95MB mỗi lần.
- Bỏ giới hạn tài nguyên dường như chỉ cải thiện bước tag ở 1.2 và 1.3 (khoảng 20 đến 24%, nhưng 1.2 tự dao động khoảng 14% giữa hai lần chạy nên con số này chưa chắc chắn); bài 2 và bài 3 gần như không đổi, nên giới hạn hiện tại không có vẻ là nút thắt của chúng.

## Bài 1. Thời gian từ đọc gold đến có bitmap tag (mỗi tag 5 đến 10 triệu user)

### limited

| Trường hợp | n | avg (ms) | p50 | p90 | p99 | min | max |
|---|---|---|---|---|---|---|---|
| 1.1 Mongo rows (đọc gold rows, lưu Mongo) | 30 | 1,730 | 1,705 | 2,139 | 2,294 | 1,251 | 2,294 |
| 1.2 Mongo agg (đọc gold agg bitmap, lưu Mongo) | 30 | 261.0 | 261.0 | 304.9 | 409.6 | 163.7 | 409.6 |
| 1.3 StarRocks (gold -> bitmap tag trong SR) | 30 | 296.1 | 268.3 | 387.6 | 711.9 | 209.6 | 711.9 |

Network và tài nguyên (docker stats): network là tổng MB trong bước và MB mỗi thao tác; service = container chạy benchmark.

| Trường hợp | service rx | service tx | Mongo tx | SR tx | rx service mỗi thao tác (MB) | CPU service avg/max (core) | CPU Mongo avg/max | CPU SR avg/max | RAM max service / Mongo / SR (GB) |
|---|---|---|---|---|---|---|---|---|---|
| 1.1 | 2,860 | 183 | 2 | 2,896 | 95.3 | 1.01 / 1.29 | 0.08 / 0.37 | 1.00 / 3.15 | 0.4 / 0.5 / 3.5 |
| 1.2 | 217 | 163 | 0 | 250 | 7.2 | 0.24 / 0.54 | 0.16 / 0.41 | 2.47 / 3.20 | 0.2 / 0.5 / 3.8 |
| 1.3 | 0 | 0 | 0 | 1 | 0.0 | 0.06 / 0.27 | 0.03 / 0.22 | 3.28 / 4.57 | 0.1 / 0.2 / 3.5 |

### unlimited

| Trường hợp | n | avg (ms) | p50 | p90 | p99 | min | max |
|---|---|---|---|---|---|---|---|
| 1.1 Mongo rows (đọc gold rows, lưu Mongo) | 30 | 1,737 | 1,717 | 2,130 | 2,200 | 1,242 | 2,200 |
| 1.2 Mongo agg (đọc gold agg bitmap, lưu Mongo) | 30 | 203.1 | 197.7 | 241.7 | 305.6 | 151.4 | 305.6 |
| 1.3 StarRocks (gold -> bitmap tag trong SR) | 30 | 225.1 | 214.0 | 263.1 | 440.1 | 175.2 | 440.1 |

Network và tài nguyên (docker stats): network là tổng MB trong bước và MB mỗi thao tác; service = container chạy benchmark.

| Trường hợp | service rx | service tx | Mongo tx | SR tx | rx service mỗi thao tác (MB) | CPU service avg/max (core) | CPU Mongo avg/max | CPU SR avg/max | RAM max service / Mongo / SR (GB) |
|---|---|---|---|---|---|---|---|---|---|
| 1.1 | 2,850 | 184 | 2 | 2,897 | 95.0 | 1.02 / 1.48 | 0.08 / 0.38 | 1.20 / 3.22 | 0.5 / 0.3 / 4.4 |
| 1.2 | 201 | 151 | 0 | 250 | 6.7 | 0.31 / 0.54 | 0.26 / 0.37 | 2.98 / 4.05 | 0.3 / 0.5 / 4.9 |
| 1.3 | 0 | 0 | 0 | 0 | 0.0 | 0.02 / 0.04 | 0.07 / 0.35 | 3.70 / 4.63 | 0.1 / 0.1 / 5.1 |

### So sánh có giới hạn và không giới hạn (p50, ms)

| Trường hợp | có giới hạn | không giới hạn | thay đổi |
|---|---|---|---|
| 1.1 Mongo rows (đọc gold rows, lưu Mongo) | 1,705 | 1,717 | +1% |
| 1.2 Mongo agg (đọc gold agg bitmap, lưu Mongo) | 261.0 | 197.7 | -24% |
| 1.3 StarRocks (gold -> bitmap tag trong SR) | 268.3 | 214.0 | -20% |

## Bài 2. Thời gian tính segment đến khi segment sẵn sàng (segment 5 đến 10 triệu user)

### limited

| Trường hợp | n | avg (ms) | p50 | p90 | p99 | min | max |
|---|---|---|---|---|---|---|---|
| 2.1 Mongo (get 10 tag, and/or/not, ghi Mongo) | 300 | 106.8 | 101.1 | 141.1 | 193.6 | 58.8 | 565.7 |
| 2.2 StarRocks (tính và lưu trong SR) | 300 | 106.5 | 104.0 | 113.5 | 206.6 | 70.5 | 281.5 |

Network và tài nguyên (docker stats): network là tổng MB trong bước và MB mỗi thao tác; service = container chạy benchmark.

| Trường hợp | service rx | service tx | Mongo tx | SR tx | rx service mỗi thao tác (MB) | CPU service avg/max (core) | CPU Mongo avg/max | CPU SR avg/max | RAM max service / Mongo / SR (GB) |
|---|---|---|---|---|---|---|---|---|---|
| 2.1 | 18,200 | 1,820 | 18,797 | 1 | 60.7 | 1.77 / 1.95 | 0.67 / 1.24 | 0.07 / 0.49 | 1.3 / 2.2 / 2.8 |
| 2.2 | 0 | 1 | 2 | 3 | 0.0 | 0.03 / 0.29 | 0.05 / 0.35 | 1.34 / 1.69 | 0.1 / 0.2 / 4.4 |

### unlimited

| Trường hợp | n | avg (ms) | p50 | p90 | p99 | min | max |
|---|---|---|---|---|---|---|---|
| 2.1 Mongo (get 10 tag, and/or/not, ghi Mongo) | 300 | 94.1 | 90.6 | 121.6 | 146.1 | 56.2 | 270.0 |
| 2.2 StarRocks (tính và lưu trong SR) | 300 | 106.4 | 103.9 | 115.5 | 181.2 | 71.6 | 282.0 |

Network và tài nguyên (docker stats): network là tổng MB trong bước và MB mỗi thao tác; service = container chạy benchmark.

| Trường hợp | service rx | service tx | Mongo tx | SR tx | rx service mỗi thao tác (MB) | CPU service avg/max (core) | CPU Mongo avg/max | CPU SR avg/max | RAM max service / Mongo / SR (GB) |
|---|---|---|---|---|---|---|---|---|---|
| 2.1 | 18,000 | 1,810 | 18,797 | 2 | 60.0 | 2.03 / 3.47 | 0.76 / 1.15 | 0.04 / 0.11 | 2.1 / 2.2 / 4.6 |
| 2.2 | 0 | 1 | 2 | 3 | 0.0 | 0.03 / 0.26 | 0.06 / 0.35 | 1.39 / 1.97 | 0.1 / 0.2 / 6.7 |

### So sánh có giới hạn và không giới hạn (p50, ms)

| Trường hợp | có giới hạn | không giới hạn | thay đổi |
|---|---|---|---|
| 2.1 Mongo (get 10 tag, and/or/not, ghi Mongo) | 101.1 | 90.6 | -10% |
| 2.2 StarRocks (tính và lưu trong SR) | 104.0 | 103.9 | -0% |

## Bài 3. Thời gian lấy toàn bộ user của segment

### limited

| Trường hợp | n | avg (ms) | p50 | p90 | p99 | min | max |
|---|---|---|---|---|---|---|---|
| 3.1 Mongo (get blob + duyệt hết user) | 40 | 43.0 | 40.7 | 52.6 | 97.4 | 32.9 | 97.4 |
| 3.2 StarRocks (SELECT unnest toàn bộ) | 40 | 1,413 | 1,388 | 1,752 | 1,915 | 1,009 | 1,915 |

Network và tài nguyên (docker stats): network là tổng MB trong bước và MB mỗi thao tác; service = container chạy benchmark.

| Trường hợp | service rx | service tx | Mongo tx | SR tx | rx service mỗi thao tác (MB) | CPU service avg/max (core) | CPU Mongo avg/max | CPU SR avg/max | RAM max service / Mongo / SR (GB) |
|---|---|---|---|---|---|---|---|---|---|
| 3.1 | 132 | 0 | 300 | 0 | 3.3 | 1.26 / 1.26 | 0.14 / 0.28 | 0.03 / 0.03 | 0.2 / 2.4 / 2.7 |
| 3.2 | 3,800 | 3 | 2 | 3,883 | 95.0 | 1.01 / 1.28 | 0.07 / 0.33 | 0.96 / 2.44 | 0.2 / 0.2 / 3.1 |

### unlimited

| Trường hợp | n | avg (ms) | p50 | p90 | p99 | min | max |
|---|---|---|---|---|---|---|---|
| 3.1 Mongo (get blob + duyệt hết user) | 40 | 40.4 | 38.9 | 43.8 | 82.9 | 32.4 | 82.9 |
| 3.2 StarRocks (SELECT unnest toàn bộ) | 40 | 1,384 | 1,392 | 1,728 | 1,887 | 980.8 | 1,887 |

Network và tài nguyên (docker stats): network là tổng MB trong bước và MB mỗi thao tác; service = container chạy benchmark.

| Trường hợp | service rx | service tx | Mongo tx | SR tx | rx service mỗi thao tác (MB) | CPU service avg/max (core) | CPU Mongo avg/max | CPU SR avg/max | RAM max service / Mongo / SR (GB) |
|---|---|---|---|---|---|---|---|---|---|
| 3.1 | 144 | 0 | 300 | 0 | 3.6 | 1.19 / 1.19 | 0.04 / 0.07 | 0.09 / 0.16 | 0.2 / 2.2 / 4.5 |
| 3.2 | 3,870 | 3 | 2 | 3,873 | 96.8 | 1.03 / 1.38 | 0.06 / 0.29 | 1.08 / 2.37 | 0.4 / 0.2 / 6.2 |

### So sánh có giới hạn và không giới hạn (p50, ms)

| Trường hợp | có giới hạn | không giới hạn | thay đổi |
|---|---|---|---|
| 3.1 Mongo (get blob + duyệt hết user) | 40.7 | 38.9 | -4% |
| 3.2 StarRocks (SELECT unnest toàn bộ) | 1,388 | 1,392 | +0% |

## Độ ổn định: bài 1.2 chạy hai lần (nhóm 1 và nhóm 2), p50 ms

| chế độ | nhóm 1 | nhóm 2 |
|---|---|---|
| limited | 261.0 | 296.6 |
| unlimited | 197.7 | 195.9 |

## Lưu ý về độ tin cậy

- Mỗi bước chạy một lần cho mỗi chế độ, nên chênh lệch nhỏ (dưới khoảng 15%, xem độ ổn định của 1.2 ở trên) có thể là nhiễu giữa các lần chạy.
- CPU, RAM, network lấy từ `docker stats` mỗi 1 đến 2 giây. Với bước ngắn (bài 1.2 và 1.3 chỉ khoảng 8 đến 12 giây) chỉ có vài mẫu, nên CPU max và RAM max thô hơn; network của docker stats có độ phân giải khoảng MB.
- Network của container Mongo, SR là tổng lưu lượng mọi kết nối của container đó (kể cả exporter Prometheus, rất nhỏ). Ở chế độ không giới hạn, các container tranh chung 10 core và RAM của Docker với nhau, nhưng các bước chạy tuần tự nên không chạy đồng thời.
- Compute của StarRocks (bài 2.2) là cả câu SQL gồm tính và ghi; không tách riêng được tính toán và ghi. Với Mongo, 2.1 gồm tải 10 tag, tính, serialize và ghi.
- Size bitmap trên StarRocks không được đo trong lượt này.

## Chi tiết các bước con

Xem `report/<chế độ>/report-g1.md`, `report-g2.md`, `report-g3.md` (từng bước con như A1 đến A7, B1) và các file `.json` kèm log trong `logs/`.
