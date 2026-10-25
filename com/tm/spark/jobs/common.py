"""Helper dùng chung cho các job (spark-submit tự thêm thư mục của script vào sys.path)."""
import os
import time

from pyspark.sql import SparkSession

DATA = os.environ.get("DATA_DIR", "/data")


def path(name):
    return f"{DATA}/{name}"


def spark_session(app, conf=None):
    b = (SparkSession.builder.appName(app)
         .config("spark.sql.session.timeZone", "UTC")
         .config("spark.sql.warehouse.dir", path("warehouse")))
    for k, v in (conf or {}).items():
        b = b.config(k, v)
    spark = b.getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    return spark


def section(title):
    print(f"\n===== {title} =====", flush=True)


def hold():
    """HOLD=<giây> giữ driver sống để xem Spark UI ở http://localhost:4040."""
    secs = int(os.environ.get("HOLD", "0"))
    if secs:
        print(f"[hold] giữ {secs}s để xem Spark UI http://localhost:4040", flush=True)
        time.sleep(secs)
