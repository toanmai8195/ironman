## Nhóm g3 (unlimited)

### 1.3 StarRocks: đọc gold, tính bitmap tag, lưu bảng bitmap

Bước đo: `B tag total: gold -> sr`, n = 30 tag, thời gian chạy 11.0s

| avg | p50 | p90 | p99 | min | max |
|---|---|---|---|---|---|
| 225.1 | 214.0 | 263.1 | 440.1 | 175.2 | 440.1 |

Tài nguyên và network trong bước (docker stats):

| container | CPU avg (core) | CPU max | RAM max (GB) | network rx (MB) | network tx (MB) | rx mỗi tag (MB) | tx mỗi tag (MB) |
|---|---|---|---|---|---|---|---|
| service | 0.02 | 0.04 | 0.13 | 0 | 0 | 0.0 | 0.0 |
| mongo | 0.07 | 0.35 | 0.08 | 0 | 0 | 0.0 | 0.0 |
| starrocks | 3.70 | 4.63 | 5.15 | 0 | 0 | 0.0 | 0.0 |

Các bước con (ms):

| bước | n | avg | p50 | p90 | p99 |
|---|---|---|---|---|---|
| B1 SR gold -> tag_bitmap | 30 | 225.1 | 214.0 | 263.1 | 440.1 |

### 2.2 Segment trên StarRocks: tính và lưu segment

Bước đo: `B total: SQL compute + store`, n = 300 segment, thời gian chạy 64.0s

| avg | p50 | p90 | p99 | min | max |
|---|---|---|---|---|---|
| 106.4 | 103.9 | 115.5 | 181.2 | 71.6 | 282.0 |

Tài nguyên và network trong bước (docker stats):

| container | CPU avg (core) | CPU max | RAM max (GB) | network rx (MB) | network tx (MB) | rx mỗi segment (MB) | tx mỗi segment (MB) |
|---|---|---|---|---|---|---|---|
| service | 0.03 | 0.26 | 0.15 | 0 | 1 | 0.0 | 0.0 |
| mongo | 0.06 | 0.35 | 0.19 | 0 | 2 | 0.0 | 0.0 |
| starrocks | 1.39 | 1.97 | 6.69 | 1 | 3 | 0.0 | 0.0 |

### 3.2 Lấy toàn bộ user của segment từ StarRocks

Bước đo: `B get all users: SQL unnest`, n = 40 lần get, thời gian chạy 56.4s

| avg | p50 | p90 | p99 | min | max |
|---|---|---|---|---|---|
| 1384.1 | 1392.5 | 1728.4 | 1887.5 | 980.8 | 1887.5 |

Tài nguyên và network trong bước (docker stats):

| container | CPU avg (core) | CPU max | RAM max (GB) | network rx (MB) | network tx (MB) | rx mỗi lần get (MB) | tx mỗi lần get (MB) |
|---|---|---|---|---|---|---|---|
| service | 1.03 | 1.38 | 0.39 | 3870 | 3 | 96.8 | 0.1 |
| mongo | 0.06 | 0.29 | 0.23 | 0 | 2 | 0.0 | 0.0 |
| starrocks | 1.08 | 2.37 | 6.22 | 3 | 3873 | 0.1 | 96.8 |
