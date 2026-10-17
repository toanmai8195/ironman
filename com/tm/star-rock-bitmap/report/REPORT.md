# Báo cáo tổng: Mongo và StarRocks cho bài toán segmentation

Report từng test: [test1-tag-rows-vs-agg.md](test1-tag-rows-vs-agg.md), [test2-tag-agg-vs-sr.md](test2-tag-agg-vs-sr.md), [test3-segment.md](test3-segment.md), [test4-getall.md](test4-getall.md), [test5-segment-hybrid.md](test5-segment-hybrid.md), [test6-sr-vs-service-cache.md](test6-sr-vs-service-cache.md), [test7-load-segment.md](test7-load-segment.md), [test8-load-segment-parallel.md](test8-load-segment-parallel.md), [test9-contains-and-page.md](test9-contains-and-page.md). Số liệu thô: `report/limited/` và `report/unlimited/`.

## Kịch bản chung

- Gold: 50 tag, 10 attribute, universe 50 triệu user, mỗi tag 5 đến 10 triệu user, cùng bảng gold cho mọi test.
- Segment: 300 segment, mỗi segment là and/or/not của 10 tag bất kỳ (seed 42), kết quả 5 đến 10 triệu user; cùng các segment cho Mongo và StarRocks.
- Mongo: bitmap lưu thành chunk tối đa 8MB, tối đa 10 chunk đọc hoặc ghi đồng thời. StarRocks: bitmap native.
- Hai chế độ: có giới hạn (StarRocks 6 CPU/8GB, Mongo 3 CPU/6GB, service 2 CPU/3GB) và không giới hạn.

## Latency p50 (ms)

| Test | Case | có giới hạn | không giới hạn |
|---|---|---|---|
| 1 | t1-rows: gold → rows → bitmap → Mongo | 1,692 | 1,692 |
| 1 | t1-agg: gold → agg → bitmap → Mongo | 233.2 | 172.4 |
| 2 | t2-agg: gold → agg → bitmap → Mongo | 258.8 | 212.3 |
| 2 | t2-sr: gold → bitmap trong StarRocks | 279.1 | 209.9 |
| 3 | t3-mongo: tag Mongo → segment Mongo | 179.5 | 154.4 |
| 3 | t3-sr: tag StarRocks → segment StarRocks | 104.6 | 105.0 |
| 4 | t4-mongo: segment Mongo → service | 46.9 | 39.5 |
| 4 | t4-sr: segment StarRocks → service | 1,378 | 1,408 |
| 5 | t5-mongo: tag Mongo → segment Mongo (chỉ Mongo) | 154.1 | 158.1 |
| 5 | t5-hybrid: tag StarRocks → segment StarRocks → Mongo (lai) | 157.4 | 157.3 |
| 6 | t6-sr: StarRocks tính + lưu, rồi lấy toàn bộ user | 1,496 | 1,521 |
| 6 | t6-cache: cache tag trong service, tính trong service | 54.3 | 57.8 |
| 7 | t7-mongo: segment trong Mongo → service | 10.5 | 10.2 |
| 7 | t7-sr: segment trong StarRocks → service | 32.3 | 29.3 |
| 8 | t8-mongo: segment trong Mongo → service (8 luồng) | 86.9 | 17.5 |
| 8 | t8-sr: segment trong StarRocks → service (8 luồng) | 77.6 | 49.8 |
| 9 | t9-contains-sr: contains trực tiếp trên StarRocks (1 luồng) | 3.4 | 3.4 |
| 9 | t9-contains-cache: contains trên cache của service (1 luồng) | 0.0 | 0.0 |
| 9 | t9-page-sr: lấy 1000 user trực tiếp trên StarRocks (1 luồng) | 29.4 | 29.2 |
| 9 | t9-page-cache: lấy 1000 user trên cache của service (1 luồng) | 0.0 | 0.0 |
| 9 | t9-contains-sr8: contains trực tiếp trên StarRocks (8 luồng) | 6.8 | 6.6 |
| 9 | t9-page-sr8: lấy 1000 user trực tiếp trên StarRocks (8 luồng) | 46.5 | 36.3 |

## Latency p90 (ms)

| Test | Case | có giới hạn | không giới hạn |
|---|---|---|---|
| 1 | t1-rows: gold → rows → bitmap → Mongo | 2,133 | 2,137 |
| 1 | t1-agg: gold → agg → bitmap → Mongo | 267.1 | 217.6 |
| 2 | t2-agg: gold → agg → bitmap → Mongo | 306.4 | 271.2 |
| 2 | t2-sr: gold → bitmap trong StarRocks | 351.0 | 280.0 |
| 3 | t3-mongo: tag Mongo → segment Mongo | 210.1 | 185.2 |
| 3 | t3-sr: tag StarRocks → segment StarRocks | 126.3 | 123.7 |
| 4 | t4-mongo: segment Mongo → service | 53.4 | 45.0 |
| 4 | t4-sr: segment StarRocks → service | 1,611 | 1,657 |
| 5 | t5-mongo: tag Mongo → segment Mongo (chỉ Mongo) | 186.0 | 186.9 |
| 5 | t5-hybrid: tag StarRocks → segment StarRocks → Mongo (lai) | 178.7 | 175.7 |
| 6 | t6-sr: StarRocks tính + lưu, rồi lấy toàn bộ user | 1,795 | 1,816 |
| 6 | t6-cache: cache tag trong service, tính trong service | 69.4 | 71.0 |
| 7 | t7-mongo: segment trong Mongo → service | 13.5 | 12.1 |
| 7 | t7-sr: segment trong StarRocks → service | 37.9 | 34.7 |
| 8 | t8-mongo: segment trong Mongo → service (8 luồng) | 99.3 | 28.2 |
| 8 | t8-sr: segment trong StarRocks → service (8 luồng) | 99.1 | 63.0 |
| 9 | t9-contains-sr: contains trực tiếp trên StarRocks (1 luồng) | 5.1 | 5.5 |
| 9 | t9-contains-cache: contains trên cache của service (1 luồng) | 0.0 | 0.0 |
| 9 | t9-page-sr: lấy 1000 user trực tiếp trên StarRocks (1 luồng) | 51.8 | 51.9 |
| 9 | t9-page-cache: lấy 1000 user trên cache của service (1 luồng) | 0.0 | 0.0 |
| 9 | t9-contains-sr8: contains trực tiếp trên StarRocks (8 luồng) | 12.0 | 9.5 |
| 9 | t9-page-sr8: lấy 1000 user trực tiếp trên StarRocks (8 luồng) | 77.8 | 61.1 |

## Latency p99 (ms)

| Test | Case | có giới hạn | không giới hạn |
|---|---|---|---|
| 1 | t1-rows: gold → rows → bitmap → Mongo | 2,214 | 2,317 |
| 1 | t1-agg: gold → agg → bitmap → Mongo | 384.7 | 311.7 |
| 2 | t2-agg: gold → agg → bitmap → Mongo | 517.8 | 393.9 |
| 2 | t2-sr: gold → bitmap trong StarRocks | 594.5 | 436.7 |
| 3 | t3-mongo: tag Mongo → segment Mongo | 242.6 | 237.8 |
| 3 | t3-sr: tag StarRocks → segment StarRocks | 196.3 | 208.0 |
| 4 | t4-mongo: segment Mongo → service | 84.9 | 77.2 |
| 4 | t4-sr: segment StarRocks → service | 1,753 | 1,798 |
| 5 | t5-mongo: tag Mongo → segment Mongo (chỉ Mongo) | 212.0 | 207.9 |
| 5 | t5-hybrid: tag StarRocks → segment StarRocks → Mongo (lai) | 247.1 | 273.1 |
| 6 | t6-sr: StarRocks tính + lưu, rồi lấy toàn bộ user | 1,887 | 1,967 |
| 6 | t6-cache: cache tag trong service, tính trong service | 76.8 | 81.7 |
| 7 | t7-mongo: segment trong Mongo → service | 21.1 | 16.8 |
| 7 | t7-sr: segment trong StarRocks → service | 47.2 | 42.8 |
| 8 | t8-mongo: segment trong Mongo → service (8 luồng) | 178.1 | 116.2 |
| 8 | t8-sr: segment trong StarRocks → service (8 luồng) | 114.8 | 86.0 |
| 9 | t9-contains-sr: contains trực tiếp trên StarRocks (1 luồng) | 9.7 | 9.3 |
| 9 | t9-contains-cache: contains trên cache của service (1 luồng) | 0.0 | 0.0 |
| 9 | t9-page-sr: lấy 1000 user trực tiếp trên StarRocks (1 luồng) | 61.8 | 62.5 |
| 9 | t9-page-cache: lấy 1000 user trên cache của service (1 luồng) | 0.1 | 0.1 |
| 9 | t9-contains-sr8: contains trực tiếp trên StarRocks (8 luồng) | 33.5 | 13.4 |
| 9 | t9-page-sr8: lấy 1000 user trực tiếp trên StarRocks (8 luồng) | 95.8 | 77.4 |

## Latency avg (ms)

| Test | Case | có giới hạn | không giới hạn |
|---|---|---|---|
| 1 | t1-rows: gold → rows → bitmap → Mongo | 1,724 | 1,732 |
| 1 | t1-agg: gold → agg → bitmap → Mongo | 230.7 | 176.8 |
| 2 | t2-agg: gold → agg → bitmap → Mongo | 264.4 | 221.4 |
| 2 | t2-sr: gold → bitmap trong StarRocks | 284.8 | 224.2 |
| 3 | t3-mongo: tag Mongo → segment Mongo | 183.3 | 158.9 |
| 3 | t3-sr: tag StarRocks → segment StarRocks | 108.9 | 109.5 |
| 4 | t4-mongo: segment Mongo → service | 46.9 | 40.4 |
| 4 | t4-sr: segment StarRocks → service | 1,379 | 1,408 |
| 5 | t5-mongo: tag Mongo → segment Mongo (chỉ Mongo) | 159.0 | 161.5 |
| 5 | t5-hybrid: tag StarRocks → segment StarRocks → Mongo (lai) | 162.3 | 162.1 |
| 6 | t6-sr: StarRocks tính + lưu, rồi lấy toàn bộ user | 1,499 | 1,525 |
| 6 | t6-cache: cache tag trong service, tính trong service | 56.4 | 58.9 |
| 7 | t7-mongo: segment trong Mongo → service | 11.2 | 10.7 |
| 7 | t7-sr: segment trong StarRocks → service | 33.0 | 30.5 |
| 8 | t8-mongo: segment trong Mongo → service (8 luồng) | 71.4 | 20.8 |
| 8 | t8-sr: segment trong StarRocks → service (8 luồng) | 76.9 | 52.0 |
| 9 | t9-contains-sr: contains trực tiếp trên StarRocks (1 luồng) | 3.8 | 3.8 |
| 9 | t9-contains-cache: contains trên cache của service (1 luồng) | 0.0 | 0.0 |
| 9 | t9-page-sr: lấy 1000 user trực tiếp trên StarRocks (1 luồng) | 29.9 | 29.9 |
| 9 | t9-page-cache: lấy 1000 user trên cache của service (1 luồng) | 0.0 | 0.0 |
| 9 | t9-contains-sr8: contains trực tiếp trên StarRocks (8 luồng) | 9.0 | 7.2 |
| 9 | t9-page-sr8: lấy 1000 user trực tiếp trên StarRocks (8 luồng) | 46.9 | 37.0 |

## Network mỗi lần đo và tài nguyên (có giới hạn)

| Test | Case | service rx mỗi lần (MB) | service tx mỗi lần (MB) | CPU service avg (core) | CPU StarRocks avg | CPU Mongo avg | RAM max StarRocks (GB) |
|---|---|---|---|---|---|---|---|
| 1 | t1-rows | 95.8 | 6.2 | 1.00 | 0.94 | 0.07 | 3.2 |
| 1 | t1-agg | 7.9 | 5.9 | 0.21 | 3.09 | 0.07 | 3.4 |
| 2 | t2-agg | 6.9 | 5.1 | 0.18 | 3.98 | 0.21 | 3.6 |
| 2 | t2-sr | 0.0 | 0.0 | 0.03 | 3.40 | 0.06 | 3.3 |
| 3 | t3-mongo | 62.7 | 6.3 | 1.02 | 0.06 | 0.41 | 2.8 |
| 3 | t3-sr | 0.0 | 0.0 | 0.03 | 1.37 | 0.06 | 4.8 |
| 4 | t4-mongo | 2.8 | 0.0 | 1.14 | 0.66 | 0.07 | 3.4 |
| 4 | t4-sr | 92.2 | 0.1 | 1.01 | 0.85 | 0.06 | 3.4 |
| 5 | t5-mongo | 60.7 | 6.1 | 1.02 | 0.06 | 0.42 | 2.9 |
| 5 | t5-hybrid | 8.2 | 6.1 | 0.18 | 1.43 | 0.10 | 4.7 |
| 6 | t6-sr | 95.3 | 0.1 | 0.93 | 1.09 | 0.06 | 3.9 |
| 6 | t6-cache | 20.9 | 0.0 | 0.86 | 0.74 | 0.04 | 3.8 |
| 7 | t7-mongo | 6.0 | 0.0 | 0.96 | 0.35 | 0.23 | 3.8 |
| 7 | t7-sr | 8.2 | 0.0 | 0.51 | 0.66 | 0.06 | 3.6 |
| 8 | t8-mongo | 6.0 | 0.0 | 2.02 | 0.04 | 0.45 | 3.1 |
| 8 | t8-sr | 7.4 | 0.0 | 2.00 | 3.13 | 0.06 | 4.2 |
| 9 | t9-contains-sr | 0.0 | 0.0 | 0.16 | 1.85 | 0.07 | 3.8 |
| 9 | t9-contains-cache | 0.3 | 0.0 | 0.74 | 0.63 | 0.00 | 3.5 |
| 9 | t9-page-sr | 0.0 | 0.0 | 0.04 | 1.12 | 0.06 | 3.3 |
| 9 | t9-page-cache | 0.4 | 0.0 | 0.75 | 0.45 | 0.09 | 3.4 |
| 9 | t9-contains-sr8 | 0.0 | 0.0 | 1.17 | 3.26 | 0.01 | 3.5 |
| 9 | t9-page-sr8 | 0.0 | 0.0 | 0.23 | 5.10 | 0.09 | 3.5 |

## Kiến trúc khuyến nghị và đánh đổi

### Kết quả 9 test (p50, ms; có giới hạn / không giới hạn)

| Test | Phương án | p50 | Ghi chú |
|---|---|---|---|
| 1. Tag, lưu Mongo | gold → rows | 1692 / 1692 | kéo khoảng 96MB mỗi tag về service |
| | gold → agg | 233 / 172 | khoảng 8MB mỗi tag |
| 2. Tag sẵn sàng | gold → agg → Mongo | 259 / 212 | |
| | gold → bitmap trong StarRocks | 279 / 210 | ngang Mongo agg (chênh dưới 10%) |
| 3. Tạo segment, lưu tại nơi tính | tag Mongo → segment Mongo | 180 / 154 | kéo khoảng 61MB về service |
| | tag StarRocks → segment StarRocks | 105 / 105 | không có network ra service |
| 4. Lấy toàn bộ user bằng `unnest` | segment Mongo → service | 47 / 40 | |
| | segment StarRocks → service (trả từng hàng) | 1378 / 1408 | khoảng 92MB mỗi lần; xem nhận xét 3 |
| 5. Segment sẵn sàng trong Mongo | chỉ Mongo | 154 / 158 | service 1,02 core |
| | StarRocks tính, xuất sang Mongo | 157 / 157 | xuất thêm khoảng 54ms; service 0,18 core |
| 6. Từ yêu cầu đến có toàn bộ user | StarRocks tính, lưu, lấy bằng `unnest` | 1496 / 1521 | |
| | tag nạp vào cache service, tính ở service | 54 / 58 | tính 30ms + duyệt user 25ms; nạp lạnh 50 tag mất khoảng 1,6 giây |
| 7. Nạp một segment lên service (cache miss), 1 luồng | từ Mongo (get chunk, giải mã) | 10,5 / 10,2 | khoảng 6,3MB; 89 / 94 lần nạp mỗi giây |
| | từ StarRocks (`bitmap_to_base64`, giải mã) | 32,3 / 29,3 | khoảng 8,3MB (base64); 30 / 33 lần nạp mỗi giây |
| 8. Nạp, 8 luồng cùng lúc | từ Mongo | 86,9 / 17,5 | 112 / 383 lần nạp mỗi giây; service dùng 2 / 6,5 core |
| | từ StarRocks | 77,6 / 49,8 | 104 / 153 lần nạp mỗi giây; StarRocks dùng 3,1 / 4,4 core |
| 9. contains | trực tiếp StarRocks (1 luồng) | 3,4 / 3,4 | 260 thao tác mỗi giây |
| | trực tiếp StarRocks (8 luồng) | 6,8 / 6,6 | 881 / 1095 thao tác mỗi giây, StarRocks dùng 3,1 đến 3,3 core |
| | cache hit trong service | 0,0007 | micro giây |
| 9. lấy 1000 user | trực tiếp StarRocks (1 luồng) | 29,4 / 29,2 | vị trí bắt đầu ngẫu nhiên, 33 thao tác mỗi giây |
| | trực tiếp StarRocks (8 luồng) | 46,5 / 36,3 | 170 / 215 thao tác mỗi giây, StarRocks dùng 5,1 đến 6,4 core (gần chạm giới hạn 6 core ở chế độ giới hạn) |
| | cache hit trong service | 0,009 | micro giây |

### Điều rút ra từ số liệu

1. **Không dùng gold → rows** (test 1): chậm hơn agg 7 đến 10 lần, tốn network gấp khoảng 12 lần.
2. **Tạo bitmap tag: StarRocks và Mongo agg ngang nhau** (test 2). Chọn StarRocks để tag nằm sẵn nơi sẽ tính segment.
3. **Lấy toàn bộ user bằng `unnest` là cách chậm, không phải đặc tính của StarRocks.** Test 4 và 6 đo `unnest` (trả từng hàng, 1,4 giây). Nạp cả bitmap từ StarRocks (test 7, khoảng 32ms) rồi duyệt trong bộ nhớ (25ms, test 6) khoảng 57ms, gần bằng 47ms của Mongo. Con số 57ms là tổng của hai phép đo riêng, chưa đo như một bước liền. Vì vậy kết luận trước đây "Mongo nhanh hơn 30 lần khi lấy toàn bộ user" chỉ đúng với cách `unnest`.
4. **Tính segment trong StarRocks cho 105ms, không cần network ra service** (test 3). Nếu segment phải nằm cả trong Mongo thì phải xuất thêm khoảng 54ms (test 5), tổng 157ms bằng Mongo thuần.
5. **Gọi thẳng StarRocks cho thao tác nhỏ đắt hơn nhiều so với cache hit.** contains 3,4ms, lấy 1000 user 29ms, và dưới tải 8 luồng, lấy 1000 user dùng 5 đến 6 core của StarRocks cho khoảng 170 đến 215 thao tác mỗi giây (khoảng 30ms CPU mỗi thao tác). Cache hit chỉ tốn micro giây.
6. **Chi phí cache miss:** từ StarRocks khoảng 29 đến 32ms, từ Mongo khoảng 10ms; Mongo nhanh hơn khoảng 3 lần. Khi service có nhiều CPU thì thông lượng nạp song song của Mongo cũng gấp 2,5 lần (383 so với 153 lần nạp mỗi giây, không giới hạn) và StarRocks không bị tải (0,05 core so với 4,4 core). Khi service chỉ có 2 CPU (chế độ giới hạn), cả hai chững lại ở khoảng 104 đến 112 lần nạp mỗi giây vì giải mã bitmap là việc CPU của service, nhưng nạp từ StarRocks vẫn tốn 3,1 core của StarRocks.
7. **Hoà vốn của việc cache:** nạp một segment rồi dùng nó từ cache rẻ hơn gọi thẳng StarRocks khi segment được dùng từ khoảng 9 lần trở lên (với contains) hoặc từ khoảng 1 lần (với lấy 1000 user); nếu nạp từ Mongo thì là khoảng 3 lần và dưới 1 lần.
8. **Cache tag trong service (test 6) cho phép không lưu segment:** nạp 50 tag (khoảng 315MB) mất 1,6 giây một lần, rồi mỗi segment tính xong trong khoảng 54ms (kèm duyệt toàn bộ user), so với 1,5 giây nếu để StarRocks tính, lưu và trả từng hàng.
9. **Giới hạn tài nguyên chỉ ảnh hưởng bước tag** (khoảng 18 đến 26%) và nạp song song (test 8); các test còn lại chênh trong nhiễu.

### Kiến trúc khuyến nghị

```
gold --(bitmap_agg trong StarRocks)--> bitmap tag (bảng StarRocks)
                                          |
                    (tính and/or/not trong StarRocks, 105ms)
                                          v
                              bitmap segment (bảng StarRocks)
                                          |
          service: Caffeine (miss: SELECT bitmap_to_base64, giải mã, ~32ms)
                                          v
              contains, lấy một trang user, lấy toàn bộ user: trên bitmap trong bộ nhớ
```

- **Tag:** gold → `bitmap_agg` trong StarRocks, lưu bảng bitmap. Không dùng gold → rows.
- **Tạo segment:** trong StarRocks (and/or/not trên bitmap native), lưu ngay trong bảng bitmap của StarRocks.
- **Phục vụ:** service dùng Caffeine; segment chưa có trong cache thì nạp cả bitmap từ StarRocks bằng `bitmap_to_base64` (khoảng 32ms, không dùng `unnest` để lấy user). Trên cache: contains, lấy trang user, lấy toàn bộ user (duyệt khoảng 25ms cho 5 đến 10 triệu user).
- **Chỉ gọi thẳng StarRocks (không cache)** cho segment ít dùng: contains khi dùng ít hơn khoảng 9 lần, lấy trang user khi dùng khoảng 1 lần. Đặt Caffeine có giới hạn trọng số (mỗi segment khoảng 6,3MB, 100 segment khoảng 630MB, 300 segment khoảng 1,9GB).
- **Không cần Mongo trong cấu hình mặc định.**

### Đánh đổi

| | A. StarRocks lưu segment, cache nạp từ StarRocks (khuyến nghị) | B. StarRocks tính, xuất sang Mongo, cache nạp từ Mongo | C. Tag cache trong service, tính tại service, không lưu segment |
|---|---|---|---|
| Ghi (tạo segment) | 105ms | 157ms (thêm 54ms xuất) | không có bước ghi |
| Cache miss (nạp segment) | khoảng 32ms, 8,3MB | khoảng 10ms, 6,3MB | 54ms mỗi segment (tính tại chỗ, tag đã nằm trong cache) |
| Tải lên StarRocks khi nạp | khoảng 0,03 core·giây mỗi lần nạp; 3,1 core ở 104 lần nạp mỗi giây | gần 0 | chỉ lúc nạp tag |
| Thông lượng nạp song song (service nhiều CPU) | 153 lần nạp mỗi giây | 383 lần nạp mỗi giây | không áp dụng |
| Số kho dữ liệu phải vận hành | 1 (StarRocks) | 2 (StarRocks và Mongo), phải giữ đồng bộ | 1 (StarRocks) |
| RAM service | cache segment (khoảng 6,3MB mỗi segment) | giống A | cache tag cố định khoảng 315MB cho 50 tag, không phụ thuộc số segment |
| CPU service | giải mã khoảng 14ms mỗi lần nạp | giống A | tính khoảng 30ms mỗi lần dùng |
| Độ tươi | segment cũ cho đến khi tính lại | giống A | tag cập nhật thì phải nạp lại cache tag |
| Điểm mạnh | đơn giản nhất, đủ tốt khi cache hit cao | nạp nhanh và rẻ hơn khi miss nhiều hoặc có nhiều service instance | không lưu và không đồng bộ segment, tính theo định nghĩa mới ngay |
| Điểm yếu | mỗi lần miss tốn CPU của StarRocks; nhiều instance thì StarRocks bị gọi nhiều | thêm một kho, thêm 54ms mỗi segment, rủi ro lệch dữ liệu giữa hai kho | tốn CPU service cho mỗi lần dùng, chỉ hợp khi segment dùng ít lần hoặc định nghĩa thay đổi liên tục |

**Khi nào chuyển từ A sang B:** Mongo tốn thêm 54ms một lần cho mỗi segment (khi tạo) và tiết kiệm khoảng 22ms mỗi lần cache miss, tức hoà vốn khi mỗi segment bị nạp từ kho khoảng 2 đến 3 lần trở lên trong vòng đời của nó. Điều đó xảy ra khi (1) có nhiều instance service, mỗi instance nạp riêng; (2) cache nhỏ so với số segment đang dùng nên bị loại thường xuyên; hoặc (3) StarRocks đã gần hết CPU. Nếu lưu lượng miss thấp, A đủ dùng.

**Khi nào chọn C:** segment dùng ít lần (một lần hoặc vài lần), hoặc định nghĩa segment thay đổi liên tục. Cache tag là chi phí cố định (khoảng 315MB RAM, 1,6 giây nạp lạnh), rồi mỗi lần dùng 54ms.

### Giới hạn của kết luận này

- **Caffeine thật chưa được đo.** Trong test, cache là bộ nhớ nạp sẵn: không có loại bỏ (eviction), không có nhiều luồng cùng miss một segment (cache stampede), không có hit ratio thực tế. Các ngưỡng hoà vốn ở trên giả định mỗi lần nạp một segment đầy đủ.
- **Tải thật chưa được đo.** Test 8 và 9 chạy 8 luồng, chỉ một loại thao tác mỗi lần. Chưa có tải hỗn hợp, nhiều service instance, hay StarRocks nhiều node.
- **Cache tag (phương án C) chỉ đo khi tag không đổi.** Chi phí cập nhật cache khi tag đổi không được đo.
- **Mỗi case chạy một lần mỗi chế độ**, nên chênh lệch dưới khoảng 15% có thể là nhiễu. CPU và RAM từ `docker stats` mỗi 1 đến 2 giây, thô với case ngắn. Network của service bị đo thiếu ở case ngắn (ví dụ test 7 Mongo: docker stats ghi service nhận 3,3MB mỗi lần trong khi Mongo gửi 6,3MB); khi đọc network nên dựa vào số gửi của nguồn (Mongo hoặc StarRocks).
- **Bitmap luôn khoảng 6,3MB** (nhỏ hơn 8MB), nên mỗi bitmap chỉ là một chunk Mongo; giới hạn 10 chunk đồng thời thực tế là 10 tag hoặc 10 segment đọc song song. Nếu universe lớn hơn, bitmap vượt 8MB thì chi phí nạp cả hai bên đều tăng.
- **Lấy trang 1000 user** ở test 9 dùng vị trí bắt đầu ngẫu nhiên (`bitmap_subset_limit`), 29ms. Ở lần đo trước dùng `unnest(...) LIMIT 1000` từ đầu bitmap, khoảng 8,5ms; chi phí phụ thuộc vị trí và cách viết câu truy vấn.
- Kịch bản là segment 5 đến 10 triệu user trên universe 50 triệu; kết quả có thể khác với segment rất nhỏ hoặc rất lớn.

