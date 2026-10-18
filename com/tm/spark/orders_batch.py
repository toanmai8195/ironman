"""Luồng Spark tối thiểu: đọc -> biến đổi -> tổng hợp -> ghi.

Chạy: xem SETUP.md. Mở http://localhost:4040 trong lúc chạy để xem DAG/stage.
"""
from pyspark.sql import SparkSession, functions as F

spark = (
    SparkSession.builder.appName("orders-batch")
    .master("local[*]")
    .config("spark.sql.shuffle.partitions", "4")  # mặc định 200, quá nhiều cho data nhỏ
    .getOrCreate()
)
spark.sparkContext.setLogLevel("WARN")

# 1. Source: dữ liệu giả (thay bằng spark.read.csv/json/parquet(...) khi cần)
orders = spark.createDataFrame(
    [
        (1, "alice", "vn", 120.0, "2026-10-01"),
        (2, "bob", "vn", 80.5, "2026-10-01"),
        (3, "alice", "vn", 45.0, "2026-10-02"),
        (4, "carol", "sg", 200.0, "2026-10-02"),
        (5, "bob", "sg", None, "2026-10-02"),  # amount null -> bị lọc
    ],
    "order_id INT, user STRING, country STRING, amount DOUBLE, order_date STRING",
)

# 2. Transform (lazy: chưa chạy gì cho tới khi gặp action)
clean = (
    orders.filter(F.col("amount").isNotNull())
    .withColumn("order_date", F.to_date("order_date"))
)

# 3. Aggregate (groupBy => shuffle => stage mới trong DAG)
daily = (
    clean.groupBy("country", "order_date")
    .agg(F.count("*").alias("orders"), F.sum("amount").alias("revenue"))
    .orderBy("country", "order_date")
)

daily.explain()  # xem physical plan
daily.show()     # action: lúc này job mới thực sự chạy

# 4. Sink
daily.write.mode("overwrite").partitionBy("country").parquet("/tmp/spark_out/daily_revenue")

# Bonus: cùng logic bằng SQL
clean.createOrReplaceTempView("orders")
spark.sql("SELECT user, SUM(amount) AS total FROM orders GROUP BY user ORDER BY total DESC").show()

input("Xong. Mở http://localhost:4040 xem Spark UI, Enter để thoát...") if __import__("sys").stdin.isatty() else None
spark.stop()
