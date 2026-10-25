# Step 06 — Spark SQL và UDF

- **File:** `jobs/06_sql_udf.py` · **Chạy:** `./run.sh step 6` (cần step 1, 2; chỉ đọc)
- **Mục đích:** dùng SQL trên DataFrame, hiểu vì sao UDF Python chậm và khi nào thay bằng built-in / higher-order function.
- **Docs:** https://spark.apache.org/docs/latest/sql-ref.html · https://spark.apache.org/docs/latest/sql-ref-functions-udf-scalar.html

## Khái niệm mới

- **Temp view:** `df.createOrReplaceTempView("t")` đặt tên cho một DataFrame để truy vấn bằng `spark.sql("... FROM t")`. Chỉ là tên gọi cho plan, không sao chép dữ liệu, mất khi hết session.
- **SQL và DataFrame API là một:** cả hai biên dịch ra cùng logical plan rồi qua Catalyst, nên hiệu năng như nhau; chọn cách dễ đọc hơn.
- **Catalog:** nơi Spark lưu metadata bảng/view/hàm (`spark.catalog.listTables()`).
- **UDF (User Defined Function):** hàm của bạn gọi trong biểu thức cột. UDF Python là hộp đen với Catalyst (không đẩy filter qua được, không tối ưu bên trong) và mỗi dòng phải được serialize sang tiến trình Python rồi quay lại, nên chậm.
- **Pandas UDF (nhắc thêm):** xử lý theo lô qua Apache Arrow nên nhanh hơn UDF thường, cần pandas và pyarrow.
- **Hàm built-in:** chạy trong JVM, được Catalyst tối ưu và sinh code; luôn ưu tiên.
- **Higher-order function:** `transform`, `filter`, `aggregate`, `exists` nhận lambda và xử lý từng phần tử của mảng ngay trong Catalyst, thay cho `explode` + `groupBy` hoặc UDF.
- **`cache()`:** giữ DataFrame trong bộ nhớ sau lần tính đầu để các lần sau không tính lại; ở đây chỉ để phép đo UDF công bằng, chi tiết ở step 08.
- **Sink `noop` (qua `timed`):** chạy toàn bộ query mà bỏ kết quả, dùng để đo thời gian thật.

| # | Mục trong file | Làm gì | Quan sát |
|---|---|---|---|
| 1 | `createOrReplaceTempView` + `spark.sql(CTE ... JOIN ... USING)` | Doanh trung bình mỗi đơn theo tier bằng SQL | View chỉ là tên cho plan, không lưu dữ liệu |
| 2 | `explain()` của SQL vs DataFrame API | Hai cách viết cùng một query | Plan giống nhau: cùng engine Catalyst |
| 3 | `COUNT(*) FILTER (WHERE ...)`, `GROUPING SETS ((device), ())` | Cú pháp SQL hay dùng | |
| 4 | `spark.catalog.listTables/listColumns` | Xem metadata | |
| 5 | `@F.udf` vs `when().otherwise()` + `timed()` trên bảng đã cache | So tốc độ UDF Python và built-in; `spark.udf.register` để gọi trong SQL | UDF chậm hơn vì mỗi dòng đi qua tiến trình Python và Catalyst không tối ưu được bên trong |
| 6 | `F.transform / filter / aggregate / exists` và bản SQL `transform(prices, p -> p + 1)` | Xử lý array bằng higher-order function | Không cần explode hay UDF |

**Quy tắc:** built-in → higher-order function → pandas UDF (Arrow, cần pandas) → Python UDF là phương án cuối.

**Bài tập:** viết `size_py` bằng `F.expr("CASE ...")`; thử đổi UDF sang `pandas_udf` (cài thêm pandas, pyarrow trong image) và so thời gian.

## Definition of Done

Xong step khi **tất cả** các ô dưới đây đúng; chưa đúng thì chưa sang step sau.

- [ ] `./run.sh step 6` chạy hết, không lỗi.
- [ ] Mục 2: hai plan SQL và DataFrame giống nhau, bạn nói được vì sao.
- [ ] Mục 5: thấy UDF chậm hơn built-in và giải thích bằng việc dữ liệu phải sang tiến trình Python.
- [ ] Viết lại được một biến đổi mảng bằng higher-order function thay cho UDF.
- [ ] Làm bài tập viết `size_py` bằng `CASE`.
