## Nhóm g3 (limited)

### 1.3 StarRocks: đọc gold, tính bitmap tag, lưu bảng bitmap

Bước đo: `B tag total: gold -> sr`, n = 30 tag, thời gian chạy 12.7s

| avg | p50 | p90 | p99 | min | max |
|---|---|---|---|---|---|
| 296.1 | 268.3 | 387.6 | 711.9 | 209.6 | 711.9 |

Tài nguyên và network trong bước (docker stats):

| container | CPU avg (core) | CPU max | RAM max (GB) | network rx (MB) | network tx (MB) | rx mỗi tag (MB) | tx mỗi tag (MB) |
|---|---|---|---|---|---|---|---|
| service | 0.06 | 0.27 | 0.11 | 0 | 0 | 0.0 | 0.0 |
| mongo | 0.03 | 0.22 | 0.22 | 0 | 0 | 0.0 | 0.0 |
| starrocks | 3.28 | 4.57 | 3.47 | 0 | 1 | 0.0 | 0.0 |

Các bước con (ms):

| bước | n | avg | p50 | p90 | p99 |
|---|---|---|---|---|---|
| B1 SR gold -> tag_bitmap | 30 | 296.1 | 268.3 | 387.6 | 711.9 |

### 2.2 Segment trên StarRocks: tính và lưu segment

Bước đo: `B total: SQL compute + store`, n = 300 segment, thời gian chạy 63.5s

| avg | p50 | p90 | p99 | min | max |
|---|---|---|---|---|---|
| 106.5 | 104.0 | 113.5 | 206.6 | 70.5 | 281.5 |

Tài nguyên và network trong bước (docker stats):

| container | CPU avg (core) | CPU max | RAM max (GB) | network rx (MB) | network tx (MB) | rx mỗi segment (MB) | tx mỗi segment (MB) |
|---|---|---|---|---|---|---|---|
| service | 0.03 | 0.29 | 0.13 | 0 | 1 | 0.0 | 0.0 |
| mongo | 0.05 | 0.35 | 0.22 | 0 | 2 | 0.0 | 0.0 |
| starrocks | 1.34 | 1.69 | 4.37 | 1 | 3 | 0.0 | 0.0 |

### 3.2 Lấy toàn bộ user của segment từ StarRocks

Bước đo: `B get all users: SQL unnest`, n = 40 lần get, thời gian chạy 57.6s

| avg | p50 | p90 | p99 | min | max |
|---|---|---|---|---|---|
| 1412.8 | 1388.0 | 1752.2 | 1914.6 | 1008.8 | 1914.6 |

Tài nguyên và network trong bước (docker stats):

| container | CPU avg (core) | CPU max | RAM max (GB) | network rx (MB) | network tx (MB) | rx mỗi lần get (MB) | tx mỗi lần get (MB) |
|---|---|---|---|---|---|---|---|
| service | 1.01 | 1.28 | 0.24 | 3800 | 3 | 95.0 | 0.1 |
| mongo | 0.07 | 0.33 | 0.22 | 0 | 2 | 0.0 | 0.1 |
| starrocks | 0.96 | 2.44 | 3.06 | 3 | 3883 | 0.1 | 97.1 |
