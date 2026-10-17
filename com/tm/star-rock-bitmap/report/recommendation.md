## Kết luận và khuyến nghị cho bài toán segmentation

### Kết quả từng test (p50, ms; có giới hạn / không giới hạn)

| Test | Mongo | StarRocks | Nhận xét |
|---|---|---|---|
| 1. Tag: gold → rows so với gold → agg (cùng lưu Mongo) | rows 1692 / 1692, agg 233 / 172 | | agg nhanh hơn rows khoảng 7 đến 10 lần; rows kéo khoảng 96MB mỗi tag về service, agg chỉ khoảng 8MB |
| 2. Tag: gold → agg → Mongo so với gold → bitmap StarRocks | 259 / 212 | 279 / 210 | gần ngang nhau (chênh dưới 10%); StarRocks không có network ra service |
| 3. Segment từ tag trong Mongo so với trong StarRocks | 180 / 154 | 105 / 105 | StarRocks nhanh hơn 1,5 đến 1,7 lần; Mongo kéo khoảng 63MB mỗi segment về service |
| 4. Lấy toàn bộ user của segment | 47 / 40 | 1378 / 1408 | Mongo nhanh hơn khoảng 29 đến 36 lần; StarRocks kéo khoảng 92MB mỗi lần (từng hàng) |

p99 (có giới hạn): test 3 Mongo 243ms, StarRocks 196ms; test 4 Mongo 85ms, StarRocks 1753ms.

### Điều rút ra từ số liệu

1. **Không dùng gold → rows.** Chậm hơn agg 7 đến 10 lần ở bước tag, tốn network gấp khoảng 12 lần, và không có lợi gì thêm (bitmap kết quả như nhau).
2. **Tạo bitmap tag: Mongo agg và StarRocks ngang nhau** (cùng quét gold trong StarRocks; phần còn lại là ghi vào Mongo khoảng 20 đến 30ms hoặc ghi vào bảng bitmap của StarRocks). Hai bên khác nhau không đáng kể so với nhiễu giữa các lần chạy, nên chọn theo nơi cần dữ liệu ở bước sau.
3. **Tính segment: StarRocks thắng.** Nó tính tại chỗ, không có network ra service (service gần như nhàn rỗi, 0,03 core). Mongo phải kéo 10 tag (khoảng 63MB) về service; trong 180ms của mỗi segment thì tải chunk chỉ khoảng 19ms, còn **giải mã và and/or/not khoảng 123ms là việc CPU trong service** (1 core). Vì thế bỏ giới hạn tài nguyên cũng chỉ cải thiện 180ms xuống 154ms. Khi cần tính nhiều segment cùng lúc, Mongo sẽ cần thêm nhiều CPU service và băng thông, còn StarRocks mở rộng bằng CPU của chính nó (khoảng 1,4 core ở nhịp 4,6 segment/giây).
4. **Lấy toàn bộ user: Mongo thắng rõ.** Mongo trả một blob khoảng 6,3MB rồi service duyệt trong bộ nhớ; StarRocks trả từng user dạng hàng qua giao thức MySQL (khoảng 92MB mỗi lần). Lưu ý: docker stats ghi service chỉ nhận khoảng 2,8MB mỗi lần ở Mongo, thấp hơn 6,3MB của blob vì case này chỉ chạy khoảng 2 giây nên thiếu mẫu; con số 6,3MB là theo kích thước blob.
5. **Giới hạn tài nguyên (StarRocks 6 CPU, Mongo 3 CPU, service 2 CPU) chỉ làm chậm bước tag** (khoảng 20 đến 26%); test 3 và 4 gần như không đổi, nên giới hạn đó đủ cho segment và đọc.

### Khuyến nghị: dùng StarRocks để tính, dùng Mongo để phục vụ

- **Tag:** gold → `bitmap_agg` trong StarRocks, giữ bitmap tag trong StarRocks (bảng bitmap). Chi phí tương đương lưu Mongo, và mở đường cho bước sau.
- **Tạo segment:** tính trong StarRocks (and/or/not trên bitmap native). Nhanh hơn, không tốn băng thông, không tốn CPU service.
- **Phục vụ và xuất toàn bộ user của segment:** sao chép bitmap segment kết quả từ StarRocks sang Mongo (chunk tối đa 8MB) cho các consumer cần lấy danh sách user, vì Mongo nhanh hơn khoảng 30 lần ở p50. Nếu việc lấy toàn bộ user hiếm, có thể đọc thẳng từ StarRocks và chấp nhận khoảng 1,4 giây mỗi lần.
- **Không nên** chạy toàn bộ trong service với Mongo (kéo tag về service để tính): chậm hơn StarRocks ở bước segment, và tốn khoảng 63MB network, khoảng 1 core service cho mỗi segment.

Cách làm thay thế đơn giản hơn nếu muốn chỉ có một kho: Mongo agg cho tag, tính segment trong service. Cách này chạy được (180ms mỗi segment) nhưng phụ thuộc vào CPU và băng thông của service khi tăng tải.

### Giới hạn của kết luận này

- Bước "sao chép segment từ StarRocks sang Mongo" **chưa được đo** trong lượt này. Ước lượng chi phí của nó gần với bước tag agg (một bitmap 6MB đi qua `bitmap_to_base64`, giải mã, ghi chunk), nhưng đó chỉ là ước lượng; cần một test riêng (test 5) trước khi chốt kiến trúc này.
- Mọi bitmap tag và segment đều khoảng 6,3MB, nhỏ hơn 8MB, nên mỗi bitmap chỉ là một chunk; giới hạn 10 chunk đồng thời thực tế là 10 tag đọc song song. Nếu universe lớn hơn (bitmap vượt 8MB) cách chia chunk mới có tác dụng và kết quả của Mongo có thể khác.
- Mỗi case chạy một lần cho mỗi chế độ, nên chênh lệch dưới khoảng 15% có thể là nhiễu (xem phần so sánh có giới hạn và không giới hạn trong từng test). CPU, RAM và network đo bằng `docker stats` mỗi 1 đến 2 giây, thô với case ngắn (test 1 agg, test 2 chỉ khoảng 10 đến 20 giây).
- Compute của StarRocks (test 3) là cả câu SQL gồm tính và ghi; Mongo gồm tải, giải mã, tính, serialize và ghi. Bước `DELETE` segment cũ của StarRocks không nằm trong thời gian đo.
- Kịch bản là segment 5 đến 10 triệu user trên universe 50 triệu; kết quả có thể khác với segment rất nhỏ hoặc rất lớn.
