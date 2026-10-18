# Test 2: tag compute, gold → agg → bitmap Mongo so với gold → bitmap trong StarRocks

Đo từ lúc bắt đầu đọc gold đến lúc bitmap tag sẵn sàng (lưu xong trong Mongo, hoặc INSERT xong vào bảng bitmap của StarRocks).

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
| t2-agg | gold → agg → bitmap → Mongo: SR gom bitmap, service giải mã rồi ghi chunk Mongo | 50 | 264.4 | 258.8 | 306.4 | 517.8 | 170.4 | 517.8 |
| t2-sr | gold → bitmap trong StarRocks: INSERT ... SELECT bitmap_agg chạy hoàn toàn trong SR | 50 | 284.8 | 279.1 | 351.0 | 594.5 | 192.8 | 594.5 |

### Network và tài nguyên

| Case | service rx (MB) | service tx (MB) | Mongo tx (MB) | SR tx (MB) | service rx mỗi tag (MB) | service tx mỗi tag (MB) |
|---|---|---|---|---|---|---|
| t2-agg | 343 | 257 | 1 | 410 | 6.9 | 5.1 |
| t2-sr | 0 | 0 | 1 | 0 | 0.0 | 0.0 |

| Case | CPU service avg / max (core) | CPU Mongo avg / max | CPU StarRocks avg / max | RAM max service / Mongo / StarRocks (GB) | thời gian chạy (s) |
|---|---|---|---|---|---|
| t2-agg | 0.18 / 0.41 | 0.21 / 0.47 | 3.98 / 4.77 | 0.3 / 0.5 / 3.6 | 14 |
| t2-sr | 0.03 / 0.23 | 0.06 / 0.32 | 3.40 / 4.35 | 0.1 / 0.5 / 3.3 | 20 |

Các bước con của t2-agg (ms):

| bước | n | avg | p50 | p90 | p99 |
|---|---|---|---|---|---|
| A1a SR agg+ship | 50 | 208.9 | 207.7 | 251.1 | 436.7 |
| A1b decode SR bitmap | 50 | 14.8 | 14.2 | 15.2 | 34.2 |
| A1 total: SR -> bitmap | 50 | 223.8 | 221.8 | 266.4 | 474.1 |
| A2 serialize | 50 | 9.9 | 9.6 | 10.8 | 16.8 |
| A3 mongo put chunks (<=8MB, <=10 parallel) | 50 | 30.6 | 26.9 | 55.4 | 61.8 |

Các bước con của t2-sr (ms):

| bước | n | avg | p50 | p90 | p99 |
|---|---|---|---|---|---|
| B1 SR gold -> tag_bitmap | 50 | 284.8 | 279.1 | 351.0 | 594.5 |

## unlimited

*Không giới hạn (StarRocks, Mongo, service dùng tối đa 10 core, RAM không giới hạn)*

### Latency (ms)

| Case | Mô tả | n | avg | p50 | p90 | p99 | min | max |
|---|---|---|---|---|---|---|---|---|
| t2-agg | gold → agg → bitmap → Mongo: SR gom bitmap, service giải mã rồi ghi chunk Mongo | 50 | 221.4 | 212.3 | 271.2 | 393.9 | 159.8 | 393.9 |
| t2-sr | gold → bitmap trong StarRocks: INSERT ... SELECT bitmap_agg chạy hoàn toàn trong SR | 50 | 224.2 | 209.9 | 280.0 | 436.7 | 179.8 | 436.7 |

### Network và tài nguyên

| Case | service rx (MB) | service tx (MB) | Mongo tx (MB) | SR tx (MB) | service rx mỗi tag (MB) | service tx mỗi tag (MB) |
|---|---|---|---|---|---|---|
| t2-agg | 409 | 308 | 1 | 418 | 8.2 | 6.2 |
| t2-sr | 0 | 0 | 1 | 0 | 0.0 | 0.0 |

| Case | CPU service avg / max (core) | CPU Mongo avg / max | CPU StarRocks avg / max | RAM max service / Mongo / StarRocks (GB) | thời gian chạy (s) |
|---|---|---|---|---|---|
| t2-agg | 0.26 / 0.64 | 0.21 / 0.52 | 4.09 / 5.81 | 0.3 / 0.5 / 5.2 | 13 |
| t2-sr | 0.05 / 0.30 | 0.09 / 0.43 | 3.26 / 4.15 | 0.1 / 0.6 / 5.1 | 17 |

Các bước con của t2-agg (ms):

| bước | n | avg | p50 | p90 | p99 |
|---|---|---|---|---|---|
| A1a SR agg+ship | 50 | 161.3 | 153.2 | 210.0 | 294.8 |
| A1b decode SR bitmap | 50 | 15.0 | 14.1 | 15.5 | 40.7 |
| A1 total: SR -> bitmap | 50 | 176.3 | 167.0 | 223.9 | 332.9 |
| A2 serialize | 50 | 11.2 | 10.8 | 11.9 | 21.8 |
| A3 mongo put chunks (<=8MB, <=10 parallel) | 50 | 33.9 | 28.0 | 57.6 | 71.3 |

Các bước con của t2-sr (ms):

| bước | n | avg | p50 | p90 | p99 |
|---|---|---|---|---|---|
| B1 SR gold -> tag_bitmap | 50 | 224.2 | 209.9 | 280.0 | 436.7 |

## So sánh có giới hạn và không giới hạn (ms)

| Case | chỉ số | có giới hạn | không giới hạn | thay đổi |
|---|---|---|---|---|
| t2-agg | avg | 264.4 | 221.4 | -16% |
| t2-agg | p50 | 258.8 | 212.3 | -18% |
| t2-agg | p90 | 306.4 | 271.2 | -12% |
| t2-agg | p99 | 517.8 | 393.9 | -24% |
| t2-sr | avg | 284.8 | 224.2 | -21% |
| t2-sr | p50 | 279.1 | 209.9 | -25% |
| t2-sr | p90 | 351.0 | 280.0 | -20% |
| t2-sr | p99 | 594.5 | 436.7 | -27% |

## Kiểm tra tính đúng

- Số user trong từng tag được in trong log lúc chạy (`report/<chế độ>/logs/`); gold giống nhau giữa các case.

## Nhận xét

- limited: p50 t2-agg = 258.8ms, t2-sr = 279.1ms; **t2-agg** nhanh hơn khoảng 1.1 lần ở p50 (p99: 517.8ms so với 594.5ms). Service nhận 6.9MB so với 0.0MB mỗi tag.
- unlimited: p50 t2-agg = 212.3ms, t2-sr = 209.9ms; **t2-sr** nhanh hơn khoảng 1.0 lần ở p50 (p99: 393.9ms so với 436.7ms). Service nhận 8.2MB so với 0.0MB mỗi tag.
