# Test 3: tính segment từ bitmap tag trong Mongo so với trong StarRocks

Đo từ lúc bắt đầu lấy bitmap tag đến lúc segment đã lưu xong. Mỗi segment là and/or/not của 10 tag bất kỳ (segment 5 đến 10 triệu user); Mongo tối đa 10 chunk đọc song song.

## Kịch bản

- Gold giống nhau cho mọi test: 50 tag, 10 attribute, universe 50 triệu user, mỗi tag 5 đến 10 triệu user.
- Số lần đo mỗi case: 300 segment. Mỗi case chạy một lần cho mỗi chế độ, trong container service riêng.
- Mongo: bitmap lưu thành chunk tối đa 8MB, tối đa 10 chunk đọc hoặc ghi đồng thời. StarRocks: bitmap native.
- CPU (core), RAM, network lấy từ `docker stats` mỗi 1 đến 2 giây trong lúc case chạy. Network là tổng của cả case, kèm mỗi lần đo.

## limited

*Có giới hạn tài nguyên (StarRocks 6 CPU/8GB, Mongo 3 CPU/6GB, service 2 CPU/3GB)*

### Latency (ms)

| Case | Mô tả | n | avg | p50 | p90 | p99 | min | max |
|---|---|---|---|---|---|---|---|---|
| t3-mongo | tag Mongo → segment Mongo: tải 10 tag, and/or/not ở service, ghi segment | 300 | 183.3 | 179.5 | 210.1 | 242.6 | 133.8 | 345.7 |
| t3-sr | tag StarRocks → segment StarRocks: một câu INSERT ... SELECT bitmap_and/or/andnot trong SR | 300 | 108.9 | 104.6 | 126.3 | 196.3 | 73.4 | 266.7 |

### Network và tài nguyên

| Case | service rx (MB) | service tx (MB) | Mongo tx (MB) | SR tx (MB) | service rx mỗi segment (MB) | service tx mỗi segment (MB) |
|---|---|---|---|---|---|---|
| t3-mongo | 18,800 | 1,890 | 18,794 | 3 | 62.7 | 6.3 |
| t3-sr | 0 | 1 | 0 | 3 | 0.0 | 0.0 |

| Case | CPU service avg / max (core) | CPU Mongo avg / max | CPU StarRocks avg / max | RAM max service / Mongo / StarRocks (GB) | thời gian chạy (s) |
|---|---|---|---|---|---|
| t3-mongo | 1.02 / 1.47 | 0.41 / 0.68 | 0.06 / 0.26 | 0.9 / 2.2 / 2.8 | 56 |
| t3-sr | 0.03 / 0.35 | 0.06 / 0.33 | 1.37 / 1.75 | 0.1 / 2.3 / 4.8 | 65 |

Các bước con của t3-mongo (ms):

| bước | n | avg | p50 | p90 | p99 |
|---|---|---|---|---|---|
| A4 fetch tag chunks (<=10 parallel) | 300 | 19.4 | 17.8 | 21.3 | 66.8 |
| A5 deserialize + and/or/not | 300 | 123.1 | 122.6 | 135.8 | 144.4 |
| A6 serialize | 300 | 9.9 | 9.4 | 11.3 | 16.1 |
| A7 mongo put chunks (<=8MB, <=10 parallel) | 300 | 31.0 | 26.1 | 54.8 | 66.6 |

## unlimited

*Không giới hạn (StarRocks, Mongo, service dùng tối đa 10 core, RAM không giới hạn)*

### Latency (ms)

| Case | Mô tả | n | avg | p50 | p90 | p99 | min | max |
|---|---|---|---|---|---|---|---|---|
| t3-mongo | tag Mongo → segment Mongo: tải 10 tag, and/or/not ở service, ghi segment | 300 | 158.9 | 154.4 | 185.2 | 237.8 | 115.4 | 326.3 |
| t3-sr | tag StarRocks → segment StarRocks: một câu INSERT ... SELECT bitmap_and/or/andnot trong SR | 300 | 109.5 | 105.0 | 123.7 | 208.0 | 78.1 | 283.6 |

### Network và tài nguyên

| Case | service rx (MB) | service tx (MB) | Mongo tx (MB) | SR tx (MB) | service rx mỗi segment (MB) | service tx mỗi segment (MB) |
|---|---|---|---|---|---|---|
| t3-mongo | 18,600 | 1,860 | 18,794 | 2 | 62.0 | 6.2 |
| t3-sr | 0 | 1 | 0 | 4 | 0.0 | 0.0 |

| Case | CPU service avg / max (core) | CPU Mongo avg / max | CPU StarRocks avg / max | RAM max service / Mongo / StarRocks (GB) | thời gian chạy (s) |
|---|---|---|---|---|---|
| t3-mongo | 1.06 / 1.83 | 0.43 / 0.97 | 0.05 / 0.17 | 1.2 / 2.3 / 4.5 | 49 |
| t3-sr | 0.03 / 0.29 | 0.07 / 0.42 | 1.34 / 1.92 | 0.2 / 2.4 / 7.6 | 65 |

Các bước con của t3-mongo (ms):

| bước | n | avg | p50 | p90 | p99 |
|---|---|---|---|---|---|
| A4 fetch tag chunks (<=10 parallel) | 300 | 19.1 | 18.1 | 21.0 | 57.4 |
| A5 deserialize + and/or/not | 300 | 100.1 | 98.9 | 111.3 | 135.6 |
| A6 serialize | 300 | 8.6 | 8.3 | 8.9 | 14.6 |
| A7 mongo put chunks (<=8MB, <=10 parallel) | 300 | 31.1 | 25.4 | 55.4 | 73.3 |

## So sánh có giới hạn và không giới hạn (ms)

| Case | chỉ số | có giới hạn | không giới hạn | thay đổi |
|---|---|---|---|---|
| t3-mongo | avg | 183.3 | 158.9 | -13% |
| t3-mongo | p50 | 179.5 | 154.4 | -14% |
| t3-mongo | p90 | 210.1 | 185.2 | -12% |
| t3-mongo | p99 | 242.6 | 237.8 | -2% |
| t3-sr | avg | 108.9 | 109.5 | +1% |
| t3-sr | p50 | 104.6 | 105.0 | +0% |
| t3-sr | p90 | 126.3 | 123.7 | -2% |
| t3-sr | p99 | 196.3 | 208.0 | +6% |

## Kiểm tra tính đúng

- limited: tổng số user của 300 segment: Mongo 2,224,721,316, StarRocks 2,224,721,316, khớp nhau.
- unlimited: tổng số user của 300 segment: Mongo 2,224,721,316, StarRocks 2,224,721,316, khớp nhau.

## Nhận xét

- limited: p50 t3-mongo = 179.5ms, t3-sr = 104.6ms; **t3-sr** nhanh hơn khoảng 1.7 lần ở p50 (p99: 242.6ms so với 196.3ms). Service nhận 62.7MB so với 0.0MB mỗi segment.
- unlimited: p50 t3-mongo = 154.4ms, t3-sr = 105.0ms; **t3-sr** nhanh hơn khoảng 1.5 lần ở p50 (p99: 237.8ms so với 208.0ms). Service nhận 62.0MB so với 0.0MB mỗi segment.
