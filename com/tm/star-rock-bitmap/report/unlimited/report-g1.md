## Nhóm g1 (unlimited)

### 1.1 Mongo rows: đọc gold rows, lưu Mongo

Bước đo: `A tag total: gold -> mongo`, n = 30 tag, thời gian chạy 53.3s

| avg | p50 | p90 | p99 | min | max |
|---|---|---|---|---|---|
| 1736.7 | 1717.1 | 2130.5 | 2199.8 | 1241.5 | 2199.8 |

Tài nguyên và network trong bước (docker stats):

| container | CPU avg (core) | CPU max | RAM max (GB) | network rx (MB) | network tx (MB) | rx mỗi tag (MB) | tx mỗi tag (MB) |
|---|---|---|---|---|---|---|---|
| service | 1.02 | 1.48 | 0.46 | 2850 | 184 | 95.0 | 6.1 |
| mongo | 0.08 | 0.38 | 0.30 | 189 | 2 | 6.3 | 0.1 |
| starrocks | 1.20 | 3.22 | 4.36 | 2 | 2897 | 0.1 | 96.6 |

Các bước con (ms):

| bước | n | avg | p50 | p90 | p99 |
|---|---|---|---|---|---|
| A1 SR scan rows+build | 30 | 1696.3 | 1667.7 | 2104.6 | 2153.3 |
| A1 total: SR -> bitmap | 30 | 1696.3 | 1667.7 | 2104.6 | 2153.3 |
| A2 serialize | 30 | 9.8 | 9.4 | 9.9 | 21.4 |
| A3 mongo put | 30 | 30.5 | 23.2 | 52.0 | 73.8 |

### 1.2 Mongo agg: đọc gold agg bitmap, lưu Mongo

Bước đo: `A tag total: gold -> mongo`, n = 30 tag, thời gian chạy 7.3s

| avg | p50 | p90 | p99 | min | max |
|---|---|---|---|---|---|
| 203.1 | 197.7 | 241.7 | 305.6 | 151.4 | 305.6 |

Tài nguyên và network trong bước (docker stats):

| container | CPU avg (core) | CPU max | RAM max (GB) | network rx (MB) | network tx (MB) | rx mỗi tag (MB) | tx mỗi tag (MB) |
|---|---|---|---|---|---|---|---|
| service | 0.31 | 0.54 | 0.28 | 201 | 151 | 6.7 | 5.0 |
| mongo | 0.26 | 0.37 | 0.50 | 188 | 0 | 6.3 | 0.0 |
| starrocks | 2.98 | 4.05 | 4.86 | 0 | 250 | 0.0 | 8.3 |

Các bước con (ms):

| bước | n | avg | p50 | p90 | p99 |
|---|---|---|---|---|---|
| A1a SR agg+ship | 30 | 141.7 | 144.9 | 172.3 | 193.8 |
| A1b decode SR bitmap | 30 | 14.7 | 13.7 | 14.9 | 29.4 |
| A1 total: SR -> bitmap | 30 | 156.5 | 158.5 | 186.2 | 224.3 |
| A2 serialize | 30 | 9.8 | 9.4 | 10.9 | 15.4 |
| A3 mongo put | 30 | 36.7 | 26.5 | 64.7 | 67.8 |
