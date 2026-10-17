# Test 5: segment chỉ Mongo so với kiến trúc lai (StarRocks tính segment, xuất sang Mongo)

Đo từ lúc bắt đầu lấy dữ liệu (Mongo: get 10 tag; lai: bắt đầu query StarRocks) đến lúc segment đã lưu xong trong Mongo, sẵn sàng cho consumer lấy toàn bộ user.

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
| t5-mongo | tag Mongo → segment Mongo (chỉ Mongo): tải 10 tag, and/or/not ở service, ghi chunk Mongo | 300 | 159.0 | 154.1 | 186.0 | 212.0 | 117.0 | 419.2 |
| t5-hybrid | tag StarRocks → segment StarRocks → Mongo (lai): SR tính và lưu segment, rồi bitmap_to_base64, giải mã, ghi chunk Mongo | 300 | 162.3 | 157.4 | 178.7 | 247.1 | 131.2 | 377.9 |

### Network và tài nguyên

| Case | service rx (MB) | service tx (MB) | Mongo tx (MB) | SR tx (MB) | service rx mỗi segment (MB) | service tx mỗi segment (MB) |
|---|---|---|---|---|---|---|
| t5-mongo | 18,200 | 1,820 | 18,794 | 2 | 60.7 | 6.1 |
| t5-hybrid | 2,460 | 1,840 | 0 | 2,503 | 8.2 | 6.1 |

| Case | CPU service avg / max (core) | CPU Mongo avg / max | CPU StarRocks avg / max | RAM max service / Mongo / StarRocks (GB) | thời gian chạy (s) |
|---|---|---|---|---|---|
| t5-mongo | 1.02 / 1.51 | 0.42 / 0.75 | 0.06 / 0.19 | 0.8 / 2.2 / 2.9 | 49 |
| t5-hybrid | 0.18 / 0.51 | 0.10 / 0.40 | 1.43 / 1.95 | 0.3 / 2.2 / 4.7 | 66 |

Các bước con của t5-mongo (ms):

| bước | n | avg | p50 | p90 | p99 |
|---|---|---|---|---|---|
| A4 fetch tag chunks (<=10 parallel) | 300 | 18.4 | 17.4 | 20.1 | 31.1 |
| A5 deserialize + and/or/not | 300 | 99.9 | 98.8 | 111.3 | 121.2 |
| A6 serialize | 300 | 9.0 | 8.8 | 9.5 | 14.2 |
| A7 mongo put chunks (<=8MB, <=10 parallel) | 300 | 31.8 | 25.5 | 55.0 | 70.9 |

Các bước con của t5-hybrid (ms):

| bước | n | avg | p50 | p90 | p99 |
|---|---|---|---|---|---|
| B total: SQL compute + store | 300 | 108.3 | 104.0 | 119.5 | 175.7 |
| B2 export: SR bitmap_to_base64 | 300 | 20.6 | 19.6 | 25.9 | 38.1 |
| B3 export: decode SR bitmap | 300 | 14.4 | 14.0 | 15.4 | 23.0 |
| B4 export: serialize | 300 | 9.5 | 9.4 | 9.9 | 11.5 |
| B5 export: mongo put chunks (<=8MB, <=10 parallel) | 300 | 9.3 | 8.2 | 14.5 | 20.0 |

## unlimited

*Không giới hạn (StarRocks, Mongo, service dùng tối đa 10 core, RAM không giới hạn)*

### Latency (ms)

| Case | Mô tả | n | avg | p50 | p90 | p99 | min | max |
|---|---|---|---|---|---|---|---|---|
| t5-mongo | tag Mongo → segment Mongo (chỉ Mongo): tải 10 tag, and/or/not ở service, ghi chunk Mongo | 300 | 161.5 | 158.1 | 186.9 | 207.9 | 117.5 | 345.4 |
| t5-hybrid | tag StarRocks → segment StarRocks → Mongo (lai): SR tính và lưu segment, rồi bitmap_to_base64, giải mã, ghi chunk Mongo | 300 | 162.1 | 157.3 | 175.7 | 273.1 | 128.6 | 386.2 |

### Network và tài nguyên

| Case | service rx (MB) | service tx (MB) | Mongo tx (MB) | SR tx (MB) | service rx mỗi segment (MB) | service tx mỗi segment (MB) |
|---|---|---|---|---|---|---|
| t5-mongo | 18,400 | 1,840 | 18,794 | 2 | 61.3 | 6.1 |
| t5-hybrid | 2,450 | 1,840 | 0 | 2,504 | 8.2 | 6.1 |

| Case | CPU service avg / max (core) | CPU Mongo avg / max | CPU StarRocks avg / max | RAM max service / Mongo / StarRocks (GB) | thời gian chạy (s) |
|---|---|---|---|---|---|
| t5-mongo | 1.04 / 1.80 | 0.43 / 0.80 | 0.05 / 0.23 | 1.1 / 2.3 / 4.6 | 50 |
| t5-hybrid | 0.19 / 0.49 | 0.10 / 0.41 | 1.50 / 1.96 | 0.3 / 2.4 / 6.7 | 66 |

Các bước con của t5-mongo (ms):

| bước | n | avg | p50 | p90 | p99 |
|---|---|---|---|---|---|
| A4 fetch tag chunks (<=10 parallel) | 300 | 19.2 | 18.1 | 21.5 | 39.5 |
| A5 deserialize + and/or/not | 300 | 101.4 | 100.8 | 113.0 | 131.5 |
| A6 serialize | 300 | 9.3 | 8.6 | 10.8 | 12.0 |
| A7 mongo put chunks (<=8MB, <=10 parallel) | 300 | 31.6 | 25.8 | 54.9 | 66.1 |

Các bước con của t5-hybrid (ms):

| bước | n | avg | p50 | p90 | p99 |
|---|---|---|---|---|---|
| B total: SQL compute + store | 300 | 107.9 | 104.2 | 119.0 | 214.3 |
| B2 export: SR bitmap_to_base64 | 300 | 21.6 | 20.3 | 27.1 | 39.9 |
| B3 export: decode SR bitmap | 300 | 14.4 | 14.0 | 15.3 | 18.4 |
| B4 export: serialize | 300 | 9.6 | 9.4 | 10.1 | 12.9 |
| B5 export: mongo put chunks (<=8MB, <=10 parallel) | 300 | 8.7 | 8.1 | 10.5 | 17.9 |

## So sánh có giới hạn và không giới hạn (ms)

| Case | chỉ số | có giới hạn | không giới hạn | thay đổi |
|---|---|---|---|---|
| t5-mongo | avg | 159.0 | 161.5 | +2% |
| t5-mongo | p50 | 154.1 | 158.1 | +3% |
| t5-mongo | p90 | 186.0 | 186.9 | +1% |
| t5-mongo | p99 | 212.0 | 207.9 | -2% |
| t5-hybrid | avg | 162.3 | 162.1 | -0% |
| t5-hybrid | p50 | 157.4 | 157.3 | -0% |
| t5-hybrid | p90 | 178.7 | 175.7 | -2% |
| t5-hybrid | p99 | 247.1 | 273.1 | +11% |

## Kiểm tra tính đúng

- limited: tổng user của segment: chỉ Mongo 2,224,721,316, StarRocks 2,224,721,316, bản xuất sang Mongo 2,224,721,316, khớp nhau.
- unlimited: tổng user của segment: chỉ Mongo 2,224,721,316, StarRocks 2,224,721,316, bản xuất sang Mongo 2,224,721,316, khớp nhau.

## Nhận xét

- limited: p50 t5-mongo = 154.1ms, t5-hybrid = 157.4ms; **t5-mongo** nhanh hơn khoảng 1.0 lần ở p50 (p99: 212.0ms so với 247.1ms). Service nhận 60.7MB so với 8.2MB mỗi segment.
- unlimited: p50 t5-mongo = 158.1ms, t5-hybrid = 157.3ms; **t5-hybrid** nhanh hơn khoảng 1.0 lần ở p50 (p99: 207.9ms so với 273.1ms). Service nhận 61.3MB so với 8.2MB mỗi segment.
