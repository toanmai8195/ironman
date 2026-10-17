# Test 4: lấy toàn bộ user của segment từ Mongo so với từ StarRocks

Đo từ lúc bắt đầu get đến lúc service có toàn bộ user của segment (5 đến 10 triệu user).

## Kịch bản

- Gold giống nhau cho mọi test: 50 tag, 10 attribute, universe 50 triệu user, mỗi tag 5 đến 10 triệu user.
- Số lần đo mỗi case: 40 lần get. Mỗi case chạy một lần cho mỗi chế độ, trong container service riêng.
- Mongo: bitmap lưu thành chunk tối đa 8MB, tối đa 10 chunk đọc hoặc ghi đồng thời. StarRocks: bitmap native.
- CPU (core), RAM, network lấy từ `docker stats` mỗi 1 đến 2 giây trong lúc case chạy. Network là tổng của cả case, kèm mỗi lần đo.

## limited

*Có giới hạn tài nguyên (StarRocks 6 CPU/8GB, Mongo 3 CPU/6GB, service 2 CPU/3GB)*

### Latency (ms)

| Case | Mô tả | n | avg | p50 | p90 | p99 | min | max |
|---|---|---|---|---|---|---|---|---|
| t4-mongo | segment Mongo → service: get chunk, giải mã, duyệt hết user | 40 | 46.9 | 46.9 | 53.4 | 84.9 | 36.2 | 84.9 |
| t4-sr | segment StarRocks → service: SELECT unnest(bitmap_to_array(bm)), trả từng hàng | 40 | 1,379 | 1,378 | 1,611 | 1,753 | 972.1 | 1,753 |

### Network và tài nguyên

| Case | service rx (MB) | service tx (MB) | Mongo tx (MB) | SR tx (MB) | service rx mỗi lần get (MB) | service tx mỗi lần get (MB) |
|---|---|---|---|---|---|---|
| t4-mongo | 113 | 0 | 300 | 0 | 2.8 | 0.0 |
| t4-sr | 3,690 | 3 | 0 | 3,830 | 92.2 | 0.1 |

| Case | CPU service avg / max (core) | CPU Mongo avg / max | CPU StarRocks avg / max | RAM max service / Mongo / StarRocks (GB) | thời gian chạy (s) |
|---|---|---|---|---|---|
| t4-mongo | 1.14 / 1.14 | 0.07 / 0.14 | 0.66 / 0.70 | 0.2 / 2.1 / 3.4 | 3 |
| t4-sr | 1.01 / 1.26 | 0.06 / 0.30 | 0.85 / 1.31 | 0.2 / 2.3 / 3.4 | 56 |

## unlimited

*Không giới hạn (StarRocks, Mongo, service dùng tối đa 10 core, RAM không giới hạn)*

### Latency (ms)

| Case | Mô tả | n | avg | p50 | p90 | p99 | min | max |
|---|---|---|---|---|---|---|---|---|
| t4-mongo | segment Mongo → service: get chunk, giải mã, duyệt hết user | 40 | 40.4 | 39.5 | 45.0 | 77.2 | 30.6 | 77.2 |
| t4-sr | segment StarRocks → service: SELECT unnest(bitmap_to_array(bm)), trả từng hàng | 40 | 1,408 | 1,408 | 1,657 | 1,798 | 997.5 | 1,798 |

### Network và tài nguyên

| Case | service rx (MB) | service tx (MB) | Mongo tx (MB) | SR tx (MB) | service rx mỗi lần get (MB) | service tx mỗi lần get (MB) |
|---|---|---|---|---|---|---|
| t4-mongo | 138 | 0 | 300 | 0 | 3.5 | 0.0 |
| t4-sr | 3,750 | 3 | 0 | 3,830 | 93.8 | 0.1 |

| Case | CPU service avg / max (core) | CPU Mongo avg / max | CPU StarRocks avg / max | RAM max service / Mongo / StarRocks (GB) | thời gian chạy (s) |
|---|---|---|---|---|---|
| t4-mongo | 1.28 / 1.28 | 0.09 / 0.17 | 0.65 / 0.65 | 0.3 / 2.4 / 6.3 | 3 |
| t4-sr | 1.02 / 1.35 | 0.06 / 0.33 | 0.82 / 1.53 | 0.3 / 2.5 / 6.3 | 58 |

## So sánh có giới hạn và không giới hạn (ms)

| Case | chỉ số | có giới hạn | không giới hạn | thay đổi |
|---|---|---|---|---|
| t4-mongo | avg | 46.9 | 40.4 | -14% |
| t4-mongo | p50 | 46.9 | 39.5 | -16% |
| t4-mongo | p90 | 53.4 | 45.0 | -16% |
| t4-mongo | p99 | 84.9 | 77.2 | -9% |
| t4-sr | avg | 1,379 | 1,408 | +2% |
| t4-sr | p50 | 1,378 | 1,408 | +2% |
| t4-sr | p90 | 1,611 | 1,657 | +3% |
| t4-sr | p99 | 1,753 | 1,798 | +3% |

## Kiểm tra tính đúng

- limited: tổng số user đọc được: Mongo 299,218,911, StarRocks 299,218,911, khớp nhau.
- unlimited: tổng số user đọc được: Mongo 299,218,911, StarRocks 299,218,911, khớp nhau.

## Nhận xét

- limited: p50 t4-mongo = 46.9ms, t4-sr = 1,378ms; **t4-mongo** nhanh hơn khoảng 29.4 lần ở p50 (p99: 84.9ms so với 1,753ms). Service nhận 2.8MB so với 92.2MB mỗi lần get.
- unlimited: p50 t4-mongo = 39.5ms, t4-sr = 1,408ms; **t4-mongo** nhanh hơn khoảng 35.7 lần ở p50 (p99: 77.2ms so với 1,798ms). Service nhận 3.5MB so với 93.8MB mỗi lần get.
