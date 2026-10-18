# Test 7: nạp segment lên service (cache miss), một luồng: từ Mongo so với từ StarRocks

Đo từ lúc bắt đầu nạp một segment đã lưu đến lúc service có bitmap trong bộ nhớ (như khi cache của service chưa có segment đó). 2000 lần nạp, mỗi lần một segment ngẫu nhiên (5 đến 10 triệu user), tuần tự một luồng. Sau khi nạp xong hai cách giống hệt nhau (RoaringBitmap trong bộ nhớ).

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
| t7-mongo | segment trong Mongo → service: get chunk, giải mã | 2000 | 11.2 | 10.5 | 13.5 | 21.1 | 9.4 | 91.3 |
| t7-sr | segment trong StarRocks → service: SELECT bitmap_to_base64(bm), giải mã | 2000 | 33.0 | 32.3 | 37.9 | 47.2 | 26.7 | 86.2 |

Thông lượng (cả case):

| Case | số lần nạp | thời gian (ms) | lần nạp mỗi giây |
|---|---|---|---|
| t7-mongo | 2000 | 22,468 | 89.0 |
| t7-sr | 2000 | 66,087 | 30.3 |

### Network và tài nguyên

| Case | service rx (MB) | service tx (MB) | Mongo tx (MB) | SR tx (MB) | service rx mỗi lần nạp (MB) | service tx mỗi lần nạp (MB) |
|---|---|---|---|---|---|---|
| t7-mongo | 12,000 | 9 | 12,491 | 10 | 6.0 | 0.0 |
| t7-sr | 16,500 | 12 | 100 | 16,680 | 8.2 | 0.0 |

| Case | CPU service avg / max (core) | CPU Mongo avg / max | CPU StarRocks avg / max | RAM max service / Mongo / StarRocks (GB) | thời gian chạy (s) |
|---|---|---|---|---|---|
| t7-mongo | 0.96 / 1.01 | 0.23 / 0.53 | 0.35 / 0.95 | 0.3 / 2.0 / 3.8 | 24 |
| t7-sr | 0.51 / 0.68 | 0.06 / 0.34 | 0.66 / 0.82 | 0.4 / 2.1 / 3.6 | 67 |

## unlimited

*Không giới hạn (StarRocks, Mongo, service dùng tối đa 10 core, RAM không giới hạn)*

### Latency (ms)

| Case | Mô tả | n | avg | p50 | p90 | p99 | min | max |
|---|---|---|---|---|---|---|---|---|
| t7-mongo | segment trong Mongo → service: get chunk, giải mã | 2000 | 10.7 | 10.2 | 12.1 | 16.8 | 9.4 | 41.1 |
| t7-sr | segment trong StarRocks → service: SELECT bitmap_to_base64(bm), giải mã | 2000 | 30.5 | 29.3 | 34.7 | 42.8 | 26.7 | 78.9 |

Thông lượng (cả case):

| Case | số lần nạp | thời gian (ms) | lần nạp mỗi giây |
|---|---|---|---|
| t7-mongo | 2000 | 21,378 | 93.6 |
| t7-sr | 2000 | 61,056 | 32.8 |

### Network và tài nguyên

| Case | service rx (MB) | service tx (MB) | Mongo tx (MB) | SR tx (MB) | service rx mỗi lần nạp (MB) | service tx mỗi lần nạp (MB) |
|---|---|---|---|---|---|---|
| t7-mongo | 11,300 | 8 | 12,492 | 10 | 5.7 | 0.0 |
| t7-sr | 16,200 | 11 | 100 | 16,680 | 8.1 | 0.0 |

| Case | CPU service avg / max (core) | CPU Mongo avg / max | CPU StarRocks avg / max | RAM max service / Mongo / StarRocks (GB) | thời gian chạy (s) |
|---|---|---|---|---|---|
| t7-mongo | 1.03 / 1.16 | 0.18 / 0.43 | 0.46 / 1.00 | 0.9 / 2.1 / 6.3 | 23 |
| t7-sr | 0.52 / 0.79 | 0.07 / 0.33 | 0.75 / 0.97 | 0.5 / 2.2 / 6.5 | 62 |

## So sánh có giới hạn và không giới hạn (ms)

| Case | chỉ số | có giới hạn | không giới hạn | thay đổi |
|---|---|---|---|---|
| t7-mongo | avg | 11.2 | 10.7 | -5% |
| t7-mongo | p50 | 10.5 | 10.2 | -3% |
| t7-mongo | p90 | 13.5 | 12.1 | -10% |
| t7-mongo | p99 | 21.1 | 16.8 | -21% |
| t7-sr | avg | 33.0 | 30.5 | -8% |
| t7-sr | p50 | 32.3 | 29.3 | -9% |
| t7-sr | p90 | 37.9 | 34.7 | -8% |
| t7-sr | p99 | 47.2 | 42.8 | -9% |

## Kiểm tra tính đúng

- limited: tổng user của các segment đã nạp: Mongo 14,812,644,024, StarRocks 14,812,644,024, khớp nhau.
- unlimited: tổng user của các segment đã nạp: Mongo 14,812,644,024, StarRocks 14,812,644,024, khớp nhau.

## Nhận xét

- limited: p50 t7-mongo = 10.5ms, t7-sr = 32.3ms; **t7-mongo** nhanh hơn khoảng 3.1 lần ở p50 (p99: 21.1ms so với 47.2ms). Service nhận 6.0MB so với 8.2MB mỗi lần nạp.
- unlimited: p50 t7-mongo = 10.2ms, t7-sr = 29.3ms; **t7-mongo** nhanh hơn khoảng 2.9 lần ở p50 (p99: 16.8ms so với 42.8ms). Service nhận 5.7MB so với 8.1MB mỗi lần nạp.
