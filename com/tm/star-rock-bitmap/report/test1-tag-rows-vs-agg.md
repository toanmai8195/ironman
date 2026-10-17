# Test 1: tag compute, gold → rows → bitmap Mongo so với gold → agg → bitmap Mongo

Đo từ lúc bắt đầu đọc gold đến lúc tag đã lưu xong trong Mongo (bitmap cắt thành chunk tối đa 8MB, tối đa 10 chunk ghi đồng thời).

## Kịch bản

- Gold giống nhau cho mọi test: 50 tag, 10 attribute, universe 50 triệu user, mỗi tag 5 đến 10 triệu user.
- Số lần đo mỗi case: 50 tag. Mỗi case chạy một lần cho mỗi chế độ, trong container service riêng.
- Mongo: bitmap lưu thành chunk tối đa 8MB, tối đa 10 chunk đọc hoặc ghi đồng thời. StarRocks: bitmap native.
- CPU (core), RAM, network lấy từ `docker stats` mỗi 1 đến 2 giây trong lúc case chạy. Network là tổng của cả case, kèm mỗi lần đo.

## limited

*Có giới hạn tài nguyên (StarRocks 6 CPU/8GB, Mongo 3 CPU/6GB, service 2 CPU/3GB)*

### Latency (ms)

| Case | Mô tả | n | avg | p50 | p90 | p99 | min | max |
|---|---|---|---|---|---|---|---|---|
| t1-rows | gold → rows → bitmap → Mongo: SR trả từng user, service build bitmap | 50 | 1,724 | 1,692 | 2,133 | 2,214 | 1,233 | 2,214 |
| t1-agg | gold → agg → bitmap → Mongo: SR gom bitmap bằng bitmap_agg, service giải mã | 50 | 230.7 | 233.2 | 267.1 | 384.7 | 149.3 | 384.7 |

### Network và tài nguyên

| Case | service rx (MB) | service tx (MB) | Mongo tx (MB) | SR tx (MB) | service rx mỗi tag (MB) | service tx mỗi tag (MB) |
|---|---|---|---|---|---|---|
| t1-rows | 4,790 | 311 | 3 | 4,845 | 95.8 | 6.2 |
| t1-agg | 393 | 295 | 1 | 420 | 7.9 | 5.9 |

| Case | CPU service avg / max (core) | CPU Mongo avg / max | CPU StarRocks avg / max | RAM max service / Mongo / StarRocks (GB) | thời gian chạy (s) |
|---|---|---|---|---|---|
| t1-rows | 1.00 / 1.40 | 0.07 / 0.35 | 0.94 / 3.31 | 0.4 / 0.4 / 3.2 | 88 |
| t1-agg | 0.21 / 0.55 | 0.07 / 0.33 | 3.09 / 4.00 | 0.3 / 0.6 / 3.4 | 13 |

Các bước con của t1-rows (ms):

| bước | n | avg | p50 | p90 | p99 |
|---|---|---|---|---|---|
| A1 SR scan rows+build | 50 | 1,686 | 1,663 | 2,090 | 2,176 |
| A1 total: SR -> bitmap | 50 | 1,686 | 1,663 | 2,090 | 2,177 |
| A2 serialize | 50 | 9.7 | 9.4 | 10.2 | 16.2 |
| A3 mongo put chunks (<=8MB, <=10 parallel) | 50 | 28.4 | 23.2 | 48.0 | 58.1 |

Các bước con của t1-agg (ms):

| bước | n | avg | p50 | p90 | p99 |
|---|---|---|---|---|---|
| A1a SR agg+ship | 50 | 199.8 | 203.3 | 238.3 | 315.6 |
| A1b decode SR bitmap | 50 | 14.2 | 13.6 | 14.5 | 33.7 |
| A1 total: SR -> bitmap | 50 | 214.1 | 216.8 | 251.8 | 350.4 |
| A2 serialize | 50 | 10.0 | 9.5 | 11.2 | 16.0 |
| A3 mongo put chunks (<=8MB, <=10 parallel) | 50 | 6.6 | 5.3 | 7.3 | 31.2 |

## unlimited

*Không giới hạn (StarRocks, Mongo, service dùng tối đa 10 core, RAM không giới hạn)*

### Latency (ms)

| Case | Mô tả | n | avg | p50 | p90 | p99 | min | max |
|---|---|---|---|---|---|---|---|---|
| t1-rows | gold → rows → bitmap → Mongo: SR trả từng user, service build bitmap | 50 | 1,732 | 1,692 | 2,137 | 2,317 | 1,227 | 2,317 |
| t1-agg | gold → agg → bitmap → Mongo: SR gom bitmap bằng bitmap_agg, service giải mã | 50 | 176.8 | 172.4 | 217.6 | 311.7 | 129.1 | 311.7 |

### Network và tài nguyên

| Case | service rx (MB) | service tx (MB) | Mongo tx (MB) | SR tx (MB) | service rx mỗi tag (MB) | service tx mỗi tag (MB) |
|---|---|---|---|---|---|---|
| t1-rows | 4,770 | 312 | 3 | 4,845 | 95.4 | 6.2 |
| t1-agg | 418 | 314 | 1 | 420 | 8.4 | 6.3 |

| Case | CPU service avg / max (core) | CPU Mongo avg / max | CPU StarRocks avg / max | RAM max service / Mongo / StarRocks (GB) | thời gian chạy (s) |
|---|---|---|---|---|---|
| t1-rows | 1.00 / 1.43 | 0.08 / 0.38 | 1.12 / 4.11 | 0.5 / 0.6 / 4.7 | 88 |
| t1-agg | 0.33 / 0.67 | 0.10 / 0.38 | 4.31 / 4.71 | 0.3 / 0.5 / 5.1 | 10 |

Các bước con của t1-rows (ms):

| bước | n | avg | p50 | p90 | p99 |
|---|---|---|---|---|---|
| A1 SR scan rows+build | 50 | 1,693 | 1,668 | 2,099 | 2,263 |
| A1 total: SR -> bitmap | 50 | 1,693 | 1,668 | 2,099 | 2,264 |
| A2 serialize | 50 | 9.3 | 8.6 | 11.0 | 15.9 |
| A3 mongo put chunks (<=8MB, <=10 parallel) | 50 | 30.0 | 24.5 | 54.7 | 66.8 |

Các bước con của t1-agg (ms):

| bước | n | avg | p50 | p90 | p99 |
|---|---|---|---|---|---|
| A1a SR agg+ship | 50 | 144.3 | 140.0 | 185.4 | 243.8 |
| A1b decode SR bitmap | 50 | 15.0 | 14.2 | 16.0 | 32.8 |
| A1 total: SR -> bitmap | 50 | 159.3 | 154.9 | 199.5 | 270.1 |
| A2 serialize | 50 | 10.7 | 10.4 | 12.4 | 19.6 |
| A3 mongo put chunks (<=8MB, <=10 parallel) | 50 | 6.8 | 5.2 | 8.0 | 30.5 |

## So sánh có giới hạn và không giới hạn (ms)

| Case | chỉ số | có giới hạn | không giới hạn | thay đổi |
|---|---|---|---|---|
| t1-rows | avg | 1,724 | 1,732 | +0% |
| t1-rows | p50 | 1,692 | 1,692 | -0% |
| t1-rows | p90 | 2,133 | 2,137 | +0% |
| t1-rows | p99 | 2,214 | 2,317 | +5% |
| t1-agg | avg | 230.7 | 176.8 | -23% |
| t1-agg | p50 | 233.2 | 172.4 | -26% |
| t1-agg | p90 | 267.1 | 217.6 | -19% |
| t1-agg | p99 | 384.7 | 311.7 | -19% |

## Kiểm tra tính đúng

- Số user trong từng tag được in trong log lúc chạy (`report/<chế độ>/logs/`); gold giống nhau giữa các case.

## Nhận xét

- limited: p50 t1-rows = 1,692ms, t1-agg = 233.2ms; **t1-agg** nhanh hơn khoảng 7.3 lần ở p50 (p99: 2,214ms so với 384.7ms). Service nhận 95.8MB so với 7.9MB mỗi tag.
- unlimited: p50 t1-rows = 1,692ms, t1-agg = 172.4ms; **t1-agg** nhanh hơn khoảng 9.8 lần ở p50 (p99: 2,317ms so với 311.7ms). Service nhận 95.4MB so với 8.4MB mỗi tag.
