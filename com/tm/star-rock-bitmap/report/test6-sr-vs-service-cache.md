# Test 6: StarRocks tính và lấy toàn bộ user so với nạp tag vào cache của service rồi tính

Đo từ lúc có yêu cầu đến lúc service có toàn bộ user của segment (100 segment, 5 đến 10 triệu user mỗi segment). t6-sr: StarRocks tính và lưu segment, rồi trả toàn bộ user về service. t6-cache: tag chỉ nằm trong StarRocks, được nạp lên cache của service (nạp lạnh toàn bộ tag đo riêng), service tính and/or/not trong bộ nhớ rồi duyệt hết user.

## Kịch bản

- Gold giống nhau cho mọi test: 50 tag, 10 attribute, universe 50 triệu user, mỗi tag 5 đến 10 triệu user.
- Số lần đo mỗi case: 100 segment. Mỗi case chạy một lần cho mỗi chế độ, trong container service riêng.
- Mongo: bitmap lưu thành chunk tối đa 8MB, tối đa 10 chunk đọc hoặc ghi đồng thời. StarRocks: bitmap native.
- CPU (core), RAM, network lấy từ `docker stats` mỗi 1 đến 2 giây trong lúc case chạy. Network là tổng của cả case, kèm mỗi lần đo.

## limited

*Có giới hạn tài nguyên (StarRocks 6 CPU/8GB, Mongo 3 CPU/6GB, service 2 CPU/3GB)*

### Latency (ms)

| Case | Mô tả | n | avg | p50 | p90 | p99 | min | max |
|---|---|---|---|---|---|---|---|---|
| t6-sr | StarRocks tính + lưu, rồi lấy toàn bộ user: INSERT ... bitmap_and/or/andnot trong SR, rồi SELECT unnest toàn bộ | 100 | 1,499 | 1,496 | 1,795 | 1,887 | 1,093 | 1,911 |
| t6-cache | cache tag trong service, tính trong service: and/or/not trên bitmap tag đã nạp sẵn trong bộ nhớ, rồi duyệt hết user | 100 | 56.4 | 54.3 | 69.4 | 76.8 | 43.0 | 82.3 |

Chi phí nạp cache (ms):

| Mô tả | n | avg | p50 | p90 | p99 |
|---|---|---|---|---|---|
| nạp lạnh toàn bộ 50 tag từ StarRocks vào cache | 5 | 1,630 | 1,585 | 1,804 | 1,804 |
| nạp một tag (bitmap_to_base64 + giải mã) | 250 | 32.6 | 31.0 | 36.7 | 51.1 |

### Network và tài nguyên

| Case | service rx (MB) | service tx (MB) | Mongo tx (MB) | SR tx (MB) | service rx mỗi segment (MB) | service tx mỗi segment (MB) |
|---|---|---|---|---|---|---|
| t6-sr | 9,530 | 8 | 5 | 9,574 | 95.3 | 0.1 |
| t6-cache | 2,090 | 1 | 1 | 2,120 | 20.9 | 0.0 |

| Case | CPU service avg / max (core) | CPU Mongo avg / max | CPU StarRocks avg / max | RAM max service / Mongo / StarRocks (GB) | thời gian chạy (s) |
|---|---|---|---|---|---|
| t6-sr | 0.93 / 1.04 | 0.06 / 0.33 | 1.09 / 1.54 | 0.2 / 0.3 / 3.9 | 154 |
| t6-cache | 0.86 / 1.17 | 0.04 / 0.26 | 0.74 / 1.03 | 0.8 / 0.2 / 3.8 | 15 |

Các bước con của t6-sr (ms):

| bước | n | avg | p50 | p90 | p99 |
|---|---|---|---|---|---|
| B total: SQL compute + store | 100 | 105.2 | 101.1 | 114.5 | 210.1 |
| B get all users: SQL unnest | 100 | 1,394 | 1,400 | 1,696 | 1,789 |

Các bước con của t6-cache (ms):

| bước | n | avg | p50 | p90 | p99 |
|---|---|---|---|---|---|
| C0 load one tag (SR bitmap_to_base64 + decode) | 250 | 32.6 | 31.0 | 36.7 | 51.1 |
| C1 cold load all tags (SR -> service cache) | 5 | 1,630 | 1,585 | 1,804 | 1,804 |
| C2 compute and/or/not (cache) | 100 | 31.0 | 29.6 | 44.0 | 53.8 |
| C3 get all users (iterate, in memory) | 100 | 25.4 | 25.3 | 30.0 | 31.8 |

## unlimited

*Không giới hạn (StarRocks, Mongo, service dùng tối đa 10 core, RAM không giới hạn)*

### Latency (ms)

| Case | Mô tả | n | avg | p50 | p90 | p99 | min | max |
|---|---|---|---|---|---|---|---|---|
| t6-sr | StarRocks tính + lưu, rồi lấy toàn bộ user: INSERT ... bitmap_and/or/andnot trong SR, rồi SELECT unnest toàn bộ | 100 | 1,525 | 1,521 | 1,816 | 1,967 | 1,130 | 2,001 |
| t6-cache | cache tag trong service, tính trong service: and/or/not trên bitmap tag đã nạp sẵn trong bộ nhớ, rồi duyệt hết user | 100 | 58.9 | 57.8 | 71.0 | 81.7 | 42.5 | 83.2 |

Chi phí nạp cache (ms):

| Mô tả | n | avg | p50 | p90 | p99 |
|---|---|---|---|---|---|
| nạp lạnh toàn bộ 50 tag từ StarRocks vào cache | 5 | 1,652 | 1,626 | 1,789 | 1,789 |
| nạp một tag (bitmap_to_base64 + giải mã) | 250 | 33.0 | 30.3 | 43.3 | 60.8 |

### Network và tài nguyên

| Case | service rx (MB) | service tx (MB) | Mongo tx (MB) | SR tx (MB) | service rx mỗi segment (MB) | service tx mỗi segment (MB) |
|---|---|---|---|---|---|---|
| t6-sr | 9,490 | 7 | 6 | 9,574 | 94.9 | 0.1 |
| t6-cache | 2,090 | 1 | 1 | 2,120 | 20.9 | 0.0 |

| Case | CPU service avg / max (core) | CPU Mongo avg / max | CPU StarRocks avg / max | RAM max service / Mongo / StarRocks (GB) | thời gian chạy (s) |
|---|---|---|---|---|---|
| t6-sr | 0.93 / 1.05 | 0.06 / 0.36 | 1.09 / 1.60 | 0.4 / 0.2 / 5.8 | 156 |
| t6-cache | 0.92 / 1.09 | 0.07 / 0.33 | 1.08 / 1.45 | 2.6 / 0.1 / 5.9 | 15 |

Các bước con của t6-sr (ms):

| bước | n | avg | p50 | p90 | p99 |
|---|---|---|---|---|---|
| B total: SQL compute + store | 100 | 104.8 | 101.7 | 119.5 | 141.4 |
| B get all users: SQL unnest | 100 | 1,420 | 1,426 | 1,700 | 1,848 |

Các bước con của t6-cache (ms):

| bước | n | avg | p50 | p90 | p99 |
|---|---|---|---|---|---|
| C0 load one tag (SR bitmap_to_base64 + decode) | 250 | 33.0 | 30.3 | 43.3 | 60.8 |
| C1 cold load all tags (SR -> service cache) | 5 | 1,652 | 1,626 | 1,789 | 1,789 |
| C2 compute and/or/not (cache) | 100 | 33.6 | 32.6 | 45.8 | 56.4 |
| C3 get all users (iterate, in memory) | 100 | 25.3 | 25.2 | 29.3 | 31.6 |

## So sánh có giới hạn và không giới hạn (ms)

| Case | chỉ số | có giới hạn | không giới hạn | thay đổi |
|---|---|---|---|---|
| t6-sr | avg | 1,499 | 1,525 | +2% |
| t6-sr | p50 | 1,496 | 1,521 | +2% |
| t6-sr | p90 | 1,795 | 1,816 | +1% |
| t6-sr | p99 | 1,887 | 1,967 | +4% |
| t6-cache | avg | 56.4 | 58.9 | +4% |
| t6-cache | p50 | 54.3 | 57.8 | +6% |
| t6-cache | p90 | 69.4 | 71.0 | +2% |
| t6-cache | p99 | 76.8 | 81.7 | +6% |

## Kiểm tra tính đúng

- limited: tổng user của 100 segment: StarRocks 748,103,101, cache trong service 748,103,101, khớp nhau.
- unlimited: tổng user của 100 segment: StarRocks 748,103,101, cache trong service 748,103,101, khớp nhau.

## Nhận xét

- limited: p50 t6-sr = 1,496ms, t6-cache = 54.3ms; **t6-cache** nhanh hơn khoảng 27.5 lần ở p50 (p99: 1,887ms so với 76.8ms). Service nhận 95.3MB so với 20.9MB mỗi segment.
- unlimited: p50 t6-sr = 1,521ms, t6-cache = 57.8ms; **t6-cache** nhanh hơn khoảng 26.3 lần ở p50 (p99: 1,967ms so với 81.7ms). Service nhận 94.9MB so với 20.9MB mỗi segment.
