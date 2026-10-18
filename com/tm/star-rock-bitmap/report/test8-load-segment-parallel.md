# Test 8: nạp segment lên service, 8 luồng cùng lúc: từ Mongo so với từ StarRocks

Như test 7 nhưng 8 luồng nạp cùng lúc (mỗi luồng một connection StarRocks; Mongo tối đa 10 chunk đồng thời), để thấy khi nhiều request cùng cache miss thì bên nào chịu tải tốt hơn. Latency là của từng lần nạp; thông lượng là số lần nạp mỗi giây của cả case.

## Kịch bản

- Gold giống nhau cho mọi test: 50 tag, 10 attribute, universe 50 triệu user, mỗi tag 5 đến 10 triệu user.
- Số lần đo mỗi case: 2000 lần nạp. Mỗi case chạy một lần cho mỗi chế độ, trong container service riêng.
- Mongo: bitmap lưu thành chunk tối đa 8MB, tối đa 10 chunk đọc hoặc ghi đồng thời. StarRocks: bitmap native.
- CPU (core), RAM, network lấy từ `docker stats` mỗi 1 đến 2 giây trong lúc case chạy. Network là tổng của cả case, kèm mỗi lần đo.

## limited

*Có giới hạn tài nguyên (StarRocks 6 CPU/8GB, Mongo 3 CPU/6GB, service 2 CPU/3GB)*

### Latency (ms)

| Case | Mô tả | n | avg | p50 | p90 | p99 | min | max |
|---|---|---|---|---|---|---|---|---|
| t8-mongo | segment trong Mongo → service (8 luồng): get chunk, giải mã | 2000 | 71.4 | 86.9 | 99.3 | 178.1 | 10.8 | 312.5 |
| t8-sr | segment trong StarRocks → service (8 luồng): SELECT bitmap_to_base64(bm), giải mã | 2000 | 76.9 | 77.6 | 99.1 | 114.8 | 33.3 | 786.5 |

Thông lượng (cả case):

| Case | số lần nạp | thời gian (ms) | lần nạp mỗi giây |
|---|---|---|---|
| t8-mongo | 2000 | 17,897 | 111.8 |
| t8-sr | 2000 | 19,294 | 103.7 |

### Network và tài nguyên

| Case | service rx (MB) | service tx (MB) | Mongo tx (MB) | SR tx (MB) | service rx mỗi lần nạp (MB) | service tx mỗi lần nạp (MB) |
|---|---|---|---|---|---|---|
| t8-mongo | 11,900 | 4 | 12,500 | 0 | 6.0 | 0.0 |
| t8-sr | 14,800 | 4 | 0 | 16,600 | 7.4 | 0.0 |

| Case | CPU service avg / max (core) | CPU Mongo avg / max | CPU StarRocks avg / max | RAM max service / Mongo / StarRocks (GB) | thời gian chạy (s) |
|---|---|---|---|---|---|
| t8-mongo | 2.02 / 2.08 | 0.45 / 0.87 | 0.04 / 0.12 | 1.5 / 2.0 / 3.1 | 19 |
| t8-sr | 2.00 / 2.07 | 0.06 / 0.34 | 3.13 / 3.64 | 0.9 / 2.0 / 4.2 | 20 |

## unlimited

*Không giới hạn (StarRocks, Mongo, service dùng tối đa 10 core, RAM không giới hạn)*

### Latency (ms)

| Case | Mô tả | n | avg | p50 | p90 | p99 | min | max |
|---|---|---|---|---|---|---|---|---|
| t8-mongo | segment trong Mongo → service (8 luồng): get chunk, giải mã | 2000 | 20.8 | 17.5 | 28.2 | 116.2 | 10.5 | 228.4 |
| t8-sr | segment trong StarRocks → service (8 luồng): SELECT bitmap_to_base64(bm), giải mã | 2000 | 52.0 | 49.8 | 63.0 | 86.0 | 32.0 | 246.9 |

Thông lượng (cả case):

| Case | số lần nạp | thời gian (ms) | lần nạp mỗi giây |
|---|---|---|---|
| t8-mongo | 2000 | 5,217 | 383.4 |
| t8-sr | 2000 | 13,035 | 153.4 |

### Network và tài nguyên

| Case | service rx (MB) | service tx (MB) | Mongo tx (MB) | SR tx (MB) | service rx mỗi lần nạp (MB) | service tx mỗi lần nạp (MB) |
|---|---|---|---|---|---|---|
| t8-mongo | 11,900 | 4 | 12,500 | 0 | 6.0 | 0.0 |
| t8-sr | 16,700 | 5 | 0 | 16,700 | 8.3 | 0.0 |

| Case | CPU service avg / max (core) | CPU Mongo avg / max | CPU StarRocks avg / max | RAM max service / Mongo / StarRocks (GB) | thời gian chạy (s) |
|---|---|---|---|---|---|
| t8-mongo | 6.53 / 6.61 | 0.85 / 1.33 | 0.05 / 0.09 | 3.5 / 2.0 / 5.3 | 6 |
| t8-sr | 2.96 / 3.43 | 0.07 / 0.38 | 4.38 / 4.71 | 1.9 / 2.0 / 6.8 | 14 |

## So sánh có giới hạn và không giới hạn (ms)

| Case | chỉ số | có giới hạn | không giới hạn | thay đổi |
|---|---|---|---|---|
| t8-mongo | avg | 71.4 | 20.8 | -71% |
| t8-mongo | p50 | 86.9 | 17.5 | -80% |
| t8-mongo | p90 | 99.3 | 28.2 | -72% |
| t8-mongo | p99 | 178.1 | 116.2 | -35% |
| t8-sr | avg | 76.9 | 52.0 | -32% |
| t8-sr | p50 | 77.6 | 49.8 | -36% |
| t8-sr | p90 | 99.1 | 63.0 | -36% |
| t8-sr | p99 | 114.8 | 86.0 | -25% |

## Kiểm tra tính đúng

- limited: tổng user của các segment đã nạp: Mongo 14,812,644,024, StarRocks 14,812,644,024, khớp nhau.
- unlimited: tổng user của các segment đã nạp: Mongo 14,812,644,024, StarRocks 14,812,644,024, khớp nhau.

## Nhận xét

- limited: p50 t8-mongo = 86.9ms, t8-sr = 77.6ms; **t8-sr** nhanh hơn khoảng 1.1 lần ở p50 (p99: 178.1ms so với 114.8ms). Service nhận 6.0MB so với 7.4MB mỗi lần nạp.
- unlimited: p50 t8-mongo = 17.5ms, t8-sr = 49.8ms; **t8-mongo** nhanh hơn khoảng 2.8 lần ở p50 (p99: 116.2ms so với 86.0ms). Service nhận 6.0MB so với 8.3MB mỗi lần nạp.
