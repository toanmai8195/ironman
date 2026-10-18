# Spark tối thiểu (PySpark, local mode)

Cần Java 17/21. Không cần cluster.

```bash
python3 -m venv .venv-spark && source .venv-spark/bin/activate
pip install pyspark
python com/tm/spark/orders_batch.py
```

Output: bảng `daily` in ra console + parquet ở `/tmp/spark_out/daily_revenue/country=*/`.

## Học gì từ file này
1. **Lazy evaluation**: `filter/withColumn/groupBy` chỉ dựng plan; `show()`/`write` mới chạy job.
2. **Shuffle**: `groupBy` tạo stage mới — xem trong `explain()` (`Exchange`) và Spark UI `:4040`.
3. **DataFrame vs SQL**: cùng engine (Catalyst), viết kiểu nào cũng được.
4. **Partition output**: `partitionBy("country")` -> thư mục theo country.

## Bước tiếp theo
- Đọc Kafka bằng Structured Streaming (`spark.readStream.format("kafka")`) từ topic Debezium của repo.
- Ghi vào Iceberg thay vì parquet.
