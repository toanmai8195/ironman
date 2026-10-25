"""STEP 01 — Sinh dữ liệu Ironshop bằng Spark (không cần file nguồn).

Ra (trong DATA_DIR, mặc định /data):
  customers, products, orders, order_items   Parquet
  events_raw                                 JSON, cố ý bẩn: trùng event_id, thiếu user_id, ts là chuỗi

Dữ liệu cố ý có "hình dạng" để các step sau có cái mà học:
  - 5% đơn dồn vào khách id=1            -> hot key, học skew ở step 04
  - khách > 45000 và sản phẩm > 2250 chưa từng bán -> học left join / anti join
  - city có NULL (1/20 khách)            -> học xử lý NULL ở step 02
  - events_raw bẩn                       -> học làm sạch ở step 02 và 10

Cấu trúc file: hằng số -> helper (pick, ts) -> build_* (mỗi hàm dựng một DataFrame, CHƯA chạy gì)
-> main() (ghi ra đĩa = lúc Spark mới thực sự chạy, rồi in kết quả).

Doc: docs/01_generate_data.md · https://spark.apache.org/docs/latest/sql-data-sources-parquet.html
"""
from typing import List

from pyspark.sql import DataFrame, SparkSession, functions as F

from common import count_files, dir_size_mb, path, section, spark_session

# Kích thước dữ liệu. Muốn chạy nhanh hơn thì giảm N_ORD / N_EVT rồi build lại image.
N_CUST, N_PROD, N_ORD, N_EVT = 50_000, 2_500, 1_000_000, 1_000_000
BUYERS = N_CUST * 9 // 10        # chỉ khách 1..45000 có đơn, 10% cuối chưa mua gì
SOLD = N_PROD * 9 // 10          # chỉ sản phẩm 1..2250 bán được, 10% cuối chưa bán


def pick(values, seed):
    """Chọn ngẫu nhiên một giá trị trong danh sách, mỗi dòng một giá trị.

    Cách làm: tạo mảng hằng số, rồi lấy phần tử ở vị trí ngẫu nhiên (element_at đếm từ 1).
    Muốn một giá trị xuất hiện nhiều hơn thì lặp nó trong danh sách (vd "free" 3 lần = 60%).
    `seed` cố định nên chạy lại cho đúng cùng dữ liệu; mỗi cột dùng seed riêng để không bị tương quan nhau.
    """
    arr = F.array(*[F.lit(v) for v in values])
    return F.element_at(arr, (F.floor(F.rand(seed) * len(values)) + 1).cast("int"))


def ts(seed, start=1_700_000_000, span=63_072_000):
    """Timestamp ngẫu nhiên trong 2 năm (span = 2 * 365 ngày tính bằng giây) kể từ 2023-11-14.

    Spark cast số nguyên (epoch giây) sang timestamp được, nên không cần hàm riêng cho ngày giờ.
    """
    return (F.lit(start) + (F.rand(seed) * span).cast("long")).cast("timestamp")


def build_customers(spark: SparkSession) -> DataFrame:
    # spark.range(1, n+1) sinh sẵn cột `id` ngay trên các executor (không đọc file nào),
    # đây là cách nhanh nhất để tạo dữ liệu giả có kích thước tuỳ ý.
    return (spark.range(1, N_CUST + 1).withColumnRenamed("id", "customer_id")
            .withColumn("email", F.concat(F.lit("user"), F.col("customer_id"), F.lit("@example.com")))
            # Cứ 20 khách thì 1 khách không có city (5% NULL). F.lit(None) một mình có kiểu NullType (Parquet không ghi được),
            # nên cast("string") cho rõ kiểu; nhánh otherwise là chuỗi nên Spark cũng tự suy ra được.
            .withColumn("city", F.when(F.col("customer_id") % 20 == 0, F.lit(None).cast("string"))
                                  .otherwise(pick(["Hanoi", "Ho Chi Minh", "Da Nang", "Hai Phong", "Can Tho"], 11)))
            .withColumn("tier", pick(["free", "free", "free", "silver", "gold"], 12))   # 60% free, 20% silver, 20% gold
            .withColumn("created_at", ts(13)))


def build_products(spark: SparkSession) -> DataFrame:
    categories = ["phones", "laptops", "audio", "fiction", "technical", "kitchen", "furniture", "cycling", "running"]
    return (spark.range(1, N_PROD + 1).withColumnRenamed("id", "product_id")
            .withColumn("category", pick(categories, 21))
            .withColumn("name", F.concat_ws(" ",
                        pick(["wireless", "compact", "premium", "durable", "smart", "classic"], 22),
                        pick(["phone", "laptop", "speaker", "keyboard", "novel", "blender", "chair"], 23)))
            .withColumn("brand", pick(["Acme", "Globex", "Initech", "Umbrella", "Hooli", "Stark"], 25))
            # Tiền dùng decimal (chính xác), không dùng double (sai số khi cộng nhiều lần)
            .withColumn("price", (F.rand(24) * 995 + 5).cast("decimal(12,2)")))


def build_orders(spark: SparkSession) -> DataFrame:
    # Hot key: 5% đơn gán cứng cho khách 1. Phần còn lại chọn khách theo phân bố lệch:
    # rand^2 dồn giá trị về gần 0, nên khách id nhỏ mua nhiều hơn khách id lớn (kiểu "khách VIP").
    hot = F.rand(31) < 0.05
    return (spark.range(1, N_ORD + 1).withColumnRenamed("id", "order_id")
            .withColumn("customer_id", F.when(hot, F.lit(1))
                                         .otherwise(1 + F.floor(F.pow(F.rand(32), 2) * BUYERS)).cast("long"))
            .withColumn("status", pick(["pending", "paid", "shipped", "delivered", "delivered", "delivered", "cancelled"], 33))
            .withColumn("created_at", ts(34))
            .withColumn("order_date", F.to_date("created_at")))   # cột ngày để partition/gom theo ngày ở step 05, 07


def build_order_items(orders: DataFrame, products: DataFrame) -> DataFrame:
    # Mỗi đơn có 1-4 dòng: sequence(1, n) sinh mảng [1..n], explode tách mảng thành n dòng.
    # order_id % 4 + 1 cho số dòng cố định theo đơn (không ngẫu nhiên) nên dữ liệu tái lập được.
    lines = orders.select("order_id", F.explode(F.sequence(F.lit(1), (F.col("order_id") % 4 + 1).cast("int"))).alias("line_no"))
    # Join với products để lấy giá: products rất nhỏ nên broadcast (gửi cho mọi executor, không shuffle bảng lớn).
    prices = F.broadcast(products.select("product_id", F.col("price").alias("unit_price")))
    return (lines
            .withColumn("product_id", (1 + F.floor(F.rand(41) * SOLD)).cast("long"))
            .withColumn("qty", (1 + F.floor(F.rand(42) * 3)).cast("int"))
            .join(prices, "product_id")
            .withColumn("line_total", F.col("qty") * F.col("unit_price"))
            .select("order_id", "line_no", "product_id", "qty", "unit_price", "line_total"))


def build_events_raw(spark: SparkSession) -> DataFrame:
    events = (spark.range(1, N_EVT + 1).withColumnRenamed("id", "event_id")
              # ~3% sự kiện không có user_id (khách chưa đăng nhập)
              .withColumn("user_id", F.when(F.rand(51) < 0.03, F.lit(None).cast("long"))
                                       .otherwise(1 + F.floor(F.pow(F.rand(52), 2) * N_CUST)).cast("long"))
              .withColumn("event_type", pick(["view", "view", "view", "view", "click", "click", "add_to_cart", "purchase"], 53))
              .withColumn("product_id", (1 + F.floor(F.rand(54) * N_PROD)).cast("long"))
              .withColumn("device", pick(["mobile", "desktop", "tablet"], 55))
              .withColumn("ts", ts(56)))
    # Tạo bản ghi trùng: lấy mẫu 1% sự kiện (cùng event_id) nối thêm vào, giống hệ thống gửi lại event khi lỗi mạng.
    raw = events.unionByName(events.sample(0.01, seed=57))
    # Ghi ts dạng chuỗi ISO như dữ liệu thô thật (JSON không có kiểu thời gian); step 02 sẽ ép lại thành timestamp.
    return raw.withColumn("ts", F.date_format("ts", "yyyy-MM-dd'T'HH:mm:ss"))


def report(spark: SparkSession, names: List[str]) -> None:
    # Đọc lại từ đĩa (không dùng DataFrame trong bộ nhớ) để chắc chắn số liệu in ra là số liệu đã ghi.
    for name in names:
        df = spark.read.json(path(name)) if name == "events_raw" else spark.read.parquet(path(name))
        print(f"{name:12s} rows={df.count():>9,}  files={count_files(path(name)):>3}  size={dir_size_mb(path(name)):.1f}MB")


def main() -> None:
    spark = spark_session("01_generate_data")

    section("Dựng các DataFrame (chưa chạy gì: transformation là lazy)")
    customers = build_customers(spark)
    products = build_products(spark)
    orders = build_orders(spark)
    items = build_order_items(orders, products)
    events_raw = build_events_raw(spark)

    section("Ghi ra đĩa (đây là action: Spark mới thực sự chạy)")
    # Mỗi partition ghi ra một file part-*.parquet nên số file đầu ra = số partition (4 khi local[4]).
    # overwrite: chạy lại được, không lỗi vì thư mục đã tồn tại.
    for name, df in [("customers", customers), ("products", products), ("orders", orders), ("order_items", items)]:
        df.write.mode("overwrite").parquet(path(name))
    # repartition(4): dùng đúng 4 file JSON để step 09 (streaming) có 4 file mà đọc dần từng file.
    events_raw.repartition(4).write.mode("overwrite").json(path("events_raw"))

    section("Kết quả")
    report(spark, ["customers", "products", "orders", "order_items", "events_raw"])


if __name__ == "__main__":
    main()
