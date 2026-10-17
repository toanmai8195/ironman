## Nhóm g2 (limited)

### 1.2 Mongo agg (lần 2, để có tag trong Mongo)

Bước đo: `A tag total: gold -> mongo`, n = 30 tag, thời gian chạy 10.6s

| avg | p50 | p90 | p99 | min | max |
|---|---|---|---|---|---|
| 302.2 | 296.6 | 364.3 | 589.3 | 187.9 | 589.3 |

Tài nguyên và network trong bước (docker stats):

| container | CPU avg (core) | CPU max | RAM max (GB) | network rx (MB) | network tx (MB) | rx mỗi tag (MB) | tx mỗi tag (MB) |
|---|---|---|---|---|---|---|---|
| service | 0.29 | 0.91 | 0.29 | 234 | 177 | 7.8 | 5.9 |
| mongo | 0.15 | 0.43 | 0.32 | 189 | 1 | 6.3 | 0.0 |
| starrocks | 2.94 | 4.08 | 3.68 | 0 | 251 | 0.0 | 8.4 |

Các bước con (ms):

| bước | n | avg | p50 | p90 | p99 |
|---|---|---|---|---|---|
| A1a SR agg+ship | 30 | 240.3 | 239.0 | 306.5 | 447.2 |
| A1b decode SR bitmap | 30 | 16.5 | 15.3 | 18.1 | 40.6 |
| A1 total: SR -> bitmap | 30 | 256.9 | 253.2 | 321.4 | 489.8 |
| A2 serialize | 30 | 10.5 | 10.0 | 11.0 | 19.6 |
| A3 mongo put | 30 | 34.8 | 31.7 | 54.0 | 80.0 |

### 2.1 Segment trên Mongo: get 10 tag, and/or/not, ghi Mongo

Bước đo: `A total (fetch+compute+store)`, n = 300 segment, thời gian chạy 33.6s

| avg | p50 | p90 | p99 | min | max |
|---|---|---|---|---|---|
| 106.8 | 101.1 | 141.1 | 193.6 | 58.8 | 565.7 |

Tài nguyên và network trong bước (docker stats):

| container | CPU avg (core) | CPU max | RAM max (GB) | network rx (MB) | network tx (MB) | rx mỗi segment (MB) | tx mỗi segment (MB) |
|---|---|---|---|---|---|---|---|
| service | 1.77 | 1.95 | 1.33 | 18200 | 1820 | 60.7 | 6.1 |
| mongo | 0.67 | 1.24 | 2.19 | 1891 | 18797 | 6.3 | 62.7 |
| starrocks | 0.07 | 0.49 | 2.79 | 0 | 1 | 0.0 | 0.0 |

Các bước con (ms):

| bước | n | avg | p50 | p90 | p99 |
|---|---|---|---|---|---|
| A4 fetch tags (parallel) | 300 | 33.4 | 27.4 | 46.4 | 116.6 |
| A5 compute and/or/not | 300 | 29.2 | 26.3 | 43.0 | 89.2 |
| A6 serialize | 300 | 10.7 | 10.0 | 11.7 | 36.2 |
| A7 mongo put segment | 300 | 33.5 | 29.2 | 59.3 | 74.6 |

### 3.1 Lấy toàn bộ user của segment từ Mongo

Bước đo: `A get all users: mongo get + iterate`, n = 40 lần get, thời gian chạy 2.6s

| avg | p50 | p90 | p99 | min | max |
|---|---|---|---|---|---|
| 43.0 | 40.7 | 52.6 | 97.4 | 32.9 | 97.4 |

Tài nguyên và network trong bước (docker stats):

| container | CPU avg (core) | CPU max | RAM max (GB) | network rx (MB) | network tx (MB) | rx mỗi lần get (MB) | tx mỗi lần get (MB) |
|---|---|---|---|---|---|---|---|
| service | 1.26 | 1.26 | 0.22 | 132 | 0 | 3.3 | 0.0 |
| mongo | 0.14 | 0.28 | 2.35 | 0 | 300 | 0.0 | 7.5 |
| starrocks | 0.03 | 0.03 | 2.74 | 0 | 0 | 0.0 | 0.0 |
