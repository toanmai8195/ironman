# Test 9: check contains và lấy một trang 1000 user: trực tiếp trên StarRocks so với từ cache của service

Hai thao tác đọc nhỏ trên một segment (working set 100 segment, 5 đến 10 triệu user mỗi segment, 2000 lần mỗi case). SR: một câu SQL mỗi lần trên bitmap trong StarRocks (`bitmap_contains`, hoặc `bitmap_subset_limit` + `unnest`). Cache: bitmap đã nạp sẵn trong bộ nhớ của service (cache hit), nên chi phí nạp lần đầu nằm ngoài các số latency (xem phần hoà vốn).

## Kịch bản

- Gold giống nhau cho mọi test; working set 100 segment, mỗi segment 5 đến 10 triệu user, mỗi case 2000 thao tác ngẫu nhiên (user hoặc vị trí bắt đầu trang ngẫu nhiên trong universe 50 triệu).
- Cùng danh sách thao tác cho StarRocks và cache nên kết quả so sánh được (số lần contains đúng, số user trong trang).
- Cache: toàn bộ 100 segment (khoảng 630MB) nạp sẵn trong bộ nhớ; nạp lần đầu tính riêng (bước C0), không nằm trong latency của cache hit.
- Số đo của cache hit rất nhỏ (micro giây) nên gồm cả chi phí đo thời gian; đọc như thứ tự độ lớn.

## limited

*Có giới hạn tài nguyên (StarRocks 6 CPU/8GB, Mongo 3 CPU/6GB, service 2 CPU/3GB)*

### Latency

| Case | n | avg | p50 | p90 | p99 | max |
|---|---|---|---|---|---|---|
| t9-contains-sr: contains trực tiếp trên StarRocks (1 luồng) | 2000 | 3.8ms | 3.4ms | 5.1ms | 9.7ms | 23.3ms |
| t9-contains-cache: contains trên cache của service (1 luồng) | 2000 | 1.0µs | 0.7µs | 1.1µs | 2.2µs | 399.8µs |
| t9-page-sr: lấy 1000 user trực tiếp trên StarRocks (1 luồng) | 2000 | 29.9ms | 29.4ms | 51.8ms | 61.8ms | 69.7ms |
| t9-page-cache: lấy 1000 user trên cache của service (1 luồng) | 2000 | 12.9µs | 8.7µs | 22.9µs | 82.2µs | 551.0µs |
| t9-contains-sr8: contains trực tiếp trên StarRocks (8 luồng) | 2000 | 9.0ms | 6.8ms | 12.0ms | 33.5ms | 195.7ms |
| t9-page-sr8: lấy 1000 user trực tiếp trên StarRocks (8 luồng) | 2000 | 46.9ms | 46.5ms | 77.8ms | 95.8ms | 143.4ms |

### Thông lượng và tài nguyên

| Case | thao tác mỗi giây | CPU StarRocks avg / max (core) | CPU service avg / max | RAM max service (GB) | StarRocks tx (MB) | service rx mỗi thao tác (KB) |
|---|---|---|---|---|---|---|
| t9-contains-sr | 260 | 1.85 / 2.72 | 0.16 / 0.43 | 0.12 | 0.8 | 0.2 |
| t9-contains-cache | 166,667 | 0.63 / 1.07 | 0.74 / 0.81 | 0.87 | 835.8 | 344.5 |
| t9-page-sr | 33 | 1.12 / 1.57 | 0.04 / 0.40 | 0.14 | 28.0 | 12.8 |
| t9-page-cache | 55,556 | 0.45 / 0.69 | 0.75 / 0.82 | 1.08 | 838.0 | 380.0 |
| t9-contains-sr8 | 881 | 3.26 / 4.34 | 1.17 / 1.17 | 0.13 | 0.0 | 0.1 |
| t9-page-sr8 | 170 | 5.10 / 6.08 | 0.23 / 0.68 | 0.16 | 20.0 | 12.1 |

Nạp 100 segment vào cache (một lần, ms mỗi segment): avg 35.3, p50 33.6, p90 45.8, p99 65.4.

### Hoà vốn của việc cache

Số lần dùng một segment trong lúc nó còn nằm trong cache để việc nạp (một lần) rẻ hơn gọi thẳng StarRocks mỗi lần: n = chi phí nạp / (latency StarRocks mỗi lần trừ latency cache hit).

| Thao tác | chi phí nạp (ms) | StarRocks mỗi lần (ms, avg) | cache hit (ms, avg) | hoà vốn n |
|---|---|---|---|---|
| contains | 35.3 | 3.82 | 0.0010 | 9.3 |
| lấy 1000 user | 35.3 | 29.89 | 0.0129 | 1.2 |

## unlimited

*Không giới hạn (StarRocks, Mongo, service dùng tối đa 10 core, RAM không giới hạn)*

### Latency

| Case | n | avg | p50 | p90 | p99 | max |
|---|---|---|---|---|---|---|
| t9-contains-sr: contains trực tiếp trên StarRocks (1 luồng) | 2000 | 3.8ms | 3.4ms | 5.5ms | 9.3ms | 22.2ms |
| t9-contains-cache: contains trên cache của service (1 luồng) | 2000 | 1.2µs | 0.9µs | 1.3µs | 2.7µs | 433.2µs |
| t9-page-sr: lấy 1000 user trực tiếp trên StarRocks (1 luồng) | 2000 | 29.9ms | 29.2ms | 51.9ms | 62.5ms | 75.7ms |
| t9-page-cache: lấy 1000 user trên cache của service (1 luồng) | 2000 | 13.8µs | 9.1µs | 25.3µs | 90.5µs | 605.0µs |
| t9-contains-sr8: contains trực tiếp trên StarRocks (8 luồng) | 2000 | 7.2ms | 6.6ms | 9.5ms | 13.4ms | 79.6ms |
| t9-page-sr8: lấy 1000 user trực tiếp trên StarRocks (8 luồng) | 2000 | 37.0ms | 36.3ms | 61.1ms | 77.4ms | 100.9ms |

### Thông lượng và tài nguyên

| Case | thao tác mỗi giây | CPU StarRocks avg / max (core) | CPU service avg / max | RAM max service (GB) | StarRocks tx (MB) | service rx mỗi thao tác (KB) |
|---|---|---|---|---|---|---|
| t9-contains-sr | 261 | 1.65 / 2.11 | 0.19 / 0.57 | 0.14 | 0.8 | 0.2 |
| t9-contains-cache | 181,818 | 0.90 / 1.62 | 1.02 / 1.16 | 0.96 | 834.9 | 309.0 |
| t9-page-sr | 33 | 1.12 / 1.62 | 0.03 / 0.33 | 0.31 | 29.0 | 12.8 |
| t9-page-cache | 54,054 | 0.54 / 0.81 | 0.84 / 0.93 | 1.08 | 838.0 | 367.5 |
| t9-contains-sr8 | 1,095 | 3.07 / 6.11 | 1.43 / 1.43 | 0.16 | 0.0 | 0.1 |
| t9-page-sr8 | 215 | 6.38 / 8.08 | 0.36 / 1.16 | 0.33 | 20.0 | 12.4 |

Nạp 100 segment vào cache (một lần, ms mỗi segment): avg 38.2, p50 33.7, p90 51.3, p99 83.5.

### Hoà vốn của việc cache

Số lần dùng một segment trong lúc nó còn nằm trong cache để việc nạp (một lần) rẻ hơn gọi thẳng StarRocks mỗi lần: n = chi phí nạp / (latency StarRocks mỗi lần trừ latency cache hit).

| Thao tác | chi phí nạp (ms) | StarRocks mỗi lần (ms, avg) | cache hit (ms, avg) | hoà vốn n |
|---|---|---|---|---|
| contains | 38.2 | 3.82 | 0.0012 | 10.0 |
| lấy 1000 user | 38.2 | 29.94 | 0.0138 | 1.3 |

## Kiểm tra tính đúng

- limited: contains đúng: StarRocks 312, cache 312, khớp nhau; user trong trang: StarRocks 2,000,000, cache 2,000,000, khớp nhau.
- unlimited: contains đúng: StarRocks 312, cache 312, khớp nhau; user trong trang: StarRocks 2,000,000, cache 2,000,000, khớp nhau.

## So sánh có giới hạn và không giới hạn (p50, avg của StarRocks trực tiếp)

| Case | có giới hạn | không giới hạn | thay đổi |
|---|---|---|---|
| t9-contains-sr | 3.4ms | 3.4ms | +1% |
| t9-contains-cache | 0.7µs | 0.9µs | +37% |
| t9-page-sr | 29.4ms | 29.2ms | -1% |
| t9-page-cache | 8.7µs | 9.1µs | +4% |
| t9-contains-sr8 | 6.8ms | 6.6ms | -2% |
| t9-page-sr8 | 46.5ms | 36.3ms | -22% |
