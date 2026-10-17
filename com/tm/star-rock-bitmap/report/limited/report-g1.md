## Nhóm g1 (limited)

### 1.1 Mongo rows: đọc gold rows, lưu Mongo

Bước đo: `A tag total: gold -> mongo`, n = 30 tag, thời gian chạy 53.1s

| avg | p50 | p90 | p99 | min | max |
|---|---|---|---|---|---|
| 1729.9 | 1705.5 | 2139.3 | 2294.1 | 1251.3 | 2294.1 |

Tài nguyên và network trong bước (docker stats):

| container | CPU avg (core) | CPU max | RAM max (GB) | network rx (MB) | network tx (MB) | rx mỗi tag (MB) | tx mỗi tag (MB) |
|---|---|---|---|---|---|---|---|
| service | 1.01 | 1.29 | 0.40 | 2860 | 183 | 95.3 | 6.1 |
| mongo | 0.08 | 0.37 | 0.45 | 189 | 2 | 6.3 | 0.1 |
| starrocks | 1.00 | 3.15 | 3.50 | 1 | 2896 | 0.0 | 96.5 |

Các bước con (ms):

| bước | n | avg | p50 | p90 | p99 |
|---|---|---|---|---|---|
| A1 SR scan rows+build | 30 | 1689.0 | 1668.0 | 2105.9 | 2199.8 |
| A1 total: SR -> bitmap | 30 | 1689.1 | 1668.0 | 2105.9 | 2201.0 |
| A2 serialize | 30 | 10.3 | 9.6 | 12.0 | 19.5 |
| A3 mongo put | 30 | 30.6 | 24.0 | 53.8 | 73.6 |

### 1.2 Mongo agg: đọc gold agg bitmap, lưu Mongo

Bước đo: `A tag total: gold -> mongo`, n = 30 tag, thời gian chạy 9.1s

| avg | p50 | p90 | p99 | min | max |
|---|---|---|---|---|---|
| 261.0 | 261.0 | 304.9 | 409.6 | 163.7 | 409.6 |

Tài nguyên và network trong bước (docker stats):

| container | CPU avg (core) | CPU max | RAM max (GB) | network rx (MB) | network tx (MB) | rx mỗi tag (MB) | tx mỗi tag (MB) |
|---|---|---|---|---|---|---|---|
| service | 0.24 | 0.54 | 0.24 | 217 | 163 | 7.2 | 5.4 |
| mongo | 0.16 | 0.41 | 0.45 | 188 | 0 | 6.3 | 0.0 |
| starrocks | 2.47 | 3.20 | 3.75 | 0 | 250 | 0.0 | 8.3 |

Các bước con (ms):

| bước | n | avg | p50 | p90 | p99 |
|---|---|---|---|---|---|
| A1a SR agg+ship | 30 | 199.5 | 201.7 | 240.5 | 282.0 |
| A1b decode SR bitmap | 30 | 14.6 | 13.5 | 14.9 | 35.5 |
| A1 total: SR -> bitmap | 30 | 214.2 | 215.2 | 254.0 | 318.7 |
| A2 serialize | 30 | 9.9 | 9.4 | 10.5 | 17.3 |
| A3 mongo put | 30 | 37.0 | 27.6 | 68.0 | 73.6 |
