## Kết luận và khuyến nghị cho bài toán segmentation

### Kết quả từng test (p50, ms; có giới hạn / không giới hạn)

| Test | Mongo | StarRocks | Nhận xét |
|---|---|---|---|
| 1. Tag: rows so với agg (cùng lưu Mongo) | rows 1692 / 1692, agg 233 / 172 | | agg nhanh hơn rows khoảng 7 đến 10 lần; rows kéo khoảng 96MB mỗi tag về service, agg chỉ khoảng 8MB |
| 2. Tag: agg → Mongo so với bitmap trong StarRocks | 259 / 212 | 279 / 210 | gần ngang nhau (chênh dưới 10%); StarRocks không có network ra service |
| 3. Tạo segment (kết quả lưu ở chính nơi tính) | 180 / 154 | 105 / 105 | StarRocks nhanh hơn khoảng 1,5 đến 1,7 lần; Mongo kéo khoảng 63MB mỗi segment về service |
| 4. Lấy toàn bộ user của segment | 47 / 40 | 1378 / 1408 | Mongo nhanh hơn khoảng 29 đến 36 lần; StarRocks kéo khoảng 92MB mỗi lần (từng hàng) |
| 5. Segment sẵn sàng trong Mongo: chỉ Mongo so với lai (SR tính, xuất sang Mongo) | chỉ Mongo 154 / 158 | lai 157 / 157 | latency gần như bằng nhau; lai: service dùng 0,18 core và nhận 8MB mỗi segment, chỉ Mongo: 1,02 core và 61MB mỗi segment |

p99 (có giới hạn): test 3 Mongo 243ms, StarRocks 196ms; test 4 Mongo 85ms, StarRocks 1753ms; test 5 chỉ Mongo 212ms, lai 247ms.

### Điều rút ra từ số liệu

1. **Không dùng gold → rows.** Chậm hơn agg 7 đến 10 lần ở bước tag, tốn network gấp khoảng 12 lần, bitmap kết quả như nhau.
2. **Tạo bitmap tag: Mongo agg và StarRocks ngang nhau.** Cả hai cùng quét gold trong StarRocks; phần còn lại (ghi Mongo khoảng 20 đến 30ms hoặc ghi bảng bitmap của StarRocks) khác nhau không đáng kể so với nhiễu giữa các lần chạy.
3. **Tạo segment: StarRocks tính nhanh hơn khi chỉ cần lưu trong StarRocks (105 so với 154 đến 180ms)**, nhưng nếu segment phải nằm trong Mongo thì bản lai tốn thêm khoảng 54ms để xuất (bitmap_to_base64 khoảng 21ms, giải mã khoảng 14ms, serialize khoảng 9ms, ghi chunk khoảng 9ms), và tổng bằng Mongo thuần (157 so với 154ms). Lợi thế của StarRocks vì vậy không nằm ở latency của một segment mà ở **tài nguyên**: service chỉ dùng 0,18 core thay vì 1,02 core, và nhận 8MB thay vì 61MB mỗi segment (Mongo thuần phải kéo 10 tag về; trong 154 đến 180ms thì tải chunk chỉ khoảng 18ms, còn giải mã và and/or/not khoảng 100 đến 123ms là việc CPU của service).
4. **Chi phí CPU mỗi segment không nghiêng hẳn về StarRocks.** Đo trên nhịp chạy tuần tự của test 5: Mongo thuần dùng khoảng 0,17 core·giây ở service và 0,07 ở Mongo (tổng khoảng 0,24), còn bản lai dùng khoảng 0,32 core·giây ở StarRocks, 0,04 ở service và 0,02 ở Mongo (tổng khoảng 0,38). Tức là bản lai tiêu tốn CPU toàn hệ thống nhiều hơn, nhưng dồn vào StarRocks và giảm mạnh network. Đây là số tính từ một luồng chạy tuần tự, không phải đo khi tải song song.
5. **Lấy toàn bộ user: Mongo thắng rõ** (khoảng 30 lần), và đây là lý do duy nhất để có Mongo trong kiến trúc. Mongo trả một blob khoảng 6,3MB rồi service duyệt trong bộ nhớ; StarRocks trả từng user dạng hàng qua giao thức MySQL (khoảng 92MB mỗi lần). Lưu ý: docker stats ghi service chỉ nhận khoảng 2,8MB mỗi lần ở Mongo, thấp hơn 6,3MB của blob vì case này chỉ chạy khoảng 2 giây nên thiếu mẫu; con số 6,3MB là theo kích thước blob.
6. **Giới hạn tài nguyên (StarRocks 6 CPU, Mongo 3 CPU, service 2 CPU) chỉ làm chậm bước tag** (khoảng 18 đến 26%). Với segment và lấy toàn bộ user, chênh lệch nằm trong nhiễu: Mongo thuần cho segment có giới hạn là 180ms ở test 3 nhưng 154ms ở test 5 (cùng cấu hình), nên mức "cải thiện khi bỏ giới hạn" ở test 3 không đáng tin.

### Khuyến nghị

**Mặc định: làm hết trong StarRocks (tag, segment đều là bitmap native trong StarRocks), không cần Mongo.** Chỉ thêm bước xuất sang Mongo nếu consumer lấy toàn bộ user của segment thường xuyên.

- **Tag:** gold → `bitmap_agg` trong StarRocks, lưu bảng bitmap. Không dùng gold → rows.
- **Tạo segment:** tính và lưu ngay trong StarRocks (and/or/not trên bitmap native): p50 khoảng 105ms mỗi segment, không có network ra service, service gần như nhàn rỗi.
- **Không có bước xuất, không có kho thứ hai:** tránh 54ms mỗi segment để xuất, tránh phải giữ Mongo và StarRocks đồng bộ, tránh vận hành thêm Mongo.
- **Lấy toàn bộ user của segment từ StarRocks:** khoảng 1,4 giây mỗi lần (5 đến 10 triệu user), kéo khoảng 92MB. Đây là điểm yếu duy nhất của cách này.

**Khi nào đáng thêm Mongo (xuất segment sang Mongo):** xuất tốn khoảng 54ms mỗi segment và tiết kiệm khoảng 1,33 giây mỗi lần lấy toàn bộ user (1378ms so với 47ms). Hoà vốn khi trung bình mỗi segment được lấy toàn bộ user từ khoảng 1 lần trên 25 segment trở lên (54 / 1330 khoảng 0,04 lần). Nếu một segment được lấy toàn bộ user nhiều hơn mức đó, hoặc consumer cần phản hồi dưới khoảng 100ms, thì nên xuất sang Mongo (kiến trúc lai: 157ms mỗi segment, bằng Mongo thuần, nhưng service dùng ít CPU hơn 5 lần và nhận ít network hơn 7 lần). Phép tính hoà vốn chỉ dựa trên latency, chưa tính chi phí lưu trữ và đồng bộ hai kho.

**Không nên chạy toàn bộ trong service với Mongo** (kéo tag về service để tính) trừ khi muốn đơn giản và lưu lượng thấp: cùng khoảng 155ms mỗi segment nhưng tốn khoảng 61MB network và khoảng 1 core service cho mỗi segment, trong khi tổng CPU mỗi segment lại thấp nhất (khoảng 0,24 core·giây, so với 0,30 của StarRocks thuần và 0,38 của bản lai).

### Giới hạn của kết luận này

- Mọi test chạy tuần tự một luồng. Hành vi dưới tải song song (nhiều segment cùng lúc, StarRocks nhiều truy vấn đồng thời, Mongo nhiều kết nối) **chưa được đo**; các phép ước tính về mở rộng ở trên chỉ là suy luận từ chi phí mỗi segment.
- Mọi bitmap tag và segment đều khoảng 6,3MB (nhỏ hơn 8MB), nên mỗi bitmap chỉ là một chunk; giới hạn 10 chunk đồng thời thực tế chỉ có nghĩa là 10 tag đọc song song. Nếu universe lớn hơn (bitmap vượt 8MB) cách chia chunk mới có tác dụng và kết quả của Mongo có thể khác.
- Mỗi case chạy một lần cho mỗi chế độ, nên chênh lệch dưới khoảng 15% có thể là nhiễu (ví dụ Mongo thuần ở test 3 và test 5). CPU, RAM và network đo bằng `docker stats` mỗi 1 đến 2 giây, thô với case ngắn (test 1 agg, test 2, test 4 Mongo chỉ khoảng 2 đến 20 giây).
- Compute của StarRocks (test 3) là cả câu SQL gồm tính và ghi; Mongo gồm tải, giải mã, tính, serialize và ghi. Bước `DELETE` segment cũ của StarRocks không nằm trong thời gian đo.
- Kịch bản là segment 5 đến 10 triệu user trên universe 50 triệu; kết quả có thể khác với segment rất nhỏ hoặc rất lớn.
