## Nhóm g2 (unlimited)

### 1.2 Mongo agg (lần 2, để có tag trong Mongo)

Bước đo: `A tag total: gold -> mongo`, n = 30 tag, thời gian chạy 7.2s

| avg | p50 | p90 | p99 | min | max |
|---|---|---|---|---|---|
| 203.0 | 195.9 | 232.5 | 388.9 | 153.0 | 388.9 |

Tài nguyên và network trong bước (docker stats):

| container | CPU avg (core) | CPU max | RAM max (GB) | network rx (MB) | network tx (MB) | rx mỗi tag (MB) | tx mỗi tag (MB) |
|---|---|---|---|---|---|---|---|
| service | 0.31 | 0.55 | 0.28 | 201 | 151 | 6.7 | 5.0 |
| mongo | 0.12 | 0.22 | 0.31 | 188 | 0 | 6.3 | 0.0 |
| starrocks | 3.69 | 5.47 | 5.08 | 0 | 251 | 0.0 | 8.4 |

Các bước con (ms):

| bước | n | avg | p50 | p90 | p99 |
|---|---|---|---|---|---|
| A1a SR agg+ship | 30 | 146.7 | 143.4 | 171.0 | 267.4 |
| A1b decode SR bitmap | 30 | 15.1 | 14.2 | 15.4 | 31.1 |
| A1 total: SR -> bitmap | 30 | 162.0 | 157.3 | 185.2 | 301.0 |
| A2 serialize | 30 | 9.9 | 9.5 | 10.5 | 17.7 |
| A3 mongo put | 30 | 31.1 | 26.0 | 51.4 | 70.1 |

### 2.1 Segment trên Mongo: get 10 tag, and/or/not, ghi Mongo

Bước đo: `A total (fetch+compute+store)`, n = 300 segment, thời gian chạy 29.8s

| avg | p50 | p90 | p99 | min | max |
|---|---|---|---|---|---|
| 94.1 | 90.6 | 121.6 | 146.1 | 56.2 | 270.0 |

Tài nguyên và network trong bước (docker stats):

| container | CPU avg (core) | CPU max | RAM max (GB) | network rx (MB) | network tx (MB) | rx mỗi segment (MB) | tx mỗi segment (MB) |
|---|---|---|---|---|---|---|---|
| service | 2.03 | 3.47 | 2.08 | 18000 | 1810 | 60.0 | 6.0 |
| mongo | 0.76 | 1.15 | 2.20 | 1892 | 18797 | 6.3 | 62.7 |
| starrocks | 0.04 | 0.11 | 4.59 | 0 | 2 | 0.0 | 0.0 |

Các bước con (ms):

| bước | n | avg | p50 | p90 | p99 |
|---|---|---|---|---|---|
| A4 fetch tags (parallel) | 300 | 25.8 | 24.2 | 29.8 | 47.8 |
| A5 compute and/or/not | 300 | 26.9 | 25.1 | 38.5 | 47.2 |
| A6 serialize | 300 | 8.8 | 8.5 | 9.7 | 12.0 |
| A7 mongo put segment | 300 | 32.6 | 27.0 | 56.2 | 83.2 |

### 3.1 Lấy toàn bộ user của segment từ Mongo

Bước đo: `A get all users: mongo get + iterate`, n = 40 lần get, thời gian chạy 2.6s

| avg | p50 | p90 | p99 | min | max |
|---|---|---|---|---|---|
| 40.4 | 38.9 | 43.8 | 82.9 | 32.4 | 82.9 |

Tài nguyên và network trong bước (docker stats):

| container | CPU avg (core) | CPU max | RAM max (GB) | network rx (MB) | network tx (MB) | rx mỗi lần get (MB) | tx mỗi lần get (MB) |
|---|---|---|---|---|---|---|---|
| service | 1.19 | 1.19 | 0.24 | 144 | 0 | 3.6 | 0.0 |
| mongo | 0.04 | 0.07 | 2.20 | 0 | 300 | 0.0 | 7.5 |
| starrocks | 0.09 | 0.16 | 4.52 | 0 | 0 | 0.0 | 0.0 |
