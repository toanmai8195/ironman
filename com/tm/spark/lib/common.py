"""Helper dùng chung cho các job (image đặt thư mục này vào PYTHONPATH).

Mỗi step chỉ thêm hàm vào đây khi step đó thực sự cần.
"""
import os
import time

from pyspark.sql import SparkSession

# Thư mục dữ liệu: trong container là /data, mount từ Docker volume ironman-spark-data (xem docker-compose.yml).
DATA = os.environ.get("DATA_DIR", "/data")


def path(name):
    """Đường dẫn của một dataset, vd path("orders") -> /data/orders."""
    return f"{DATA}/{name}"


def spark_session(app, conf=None):
    """Tạo (hoặc lấy lại) SparkSession. `conf` là dict cấu hình riêng của job, vd {"spark.sql.shuffle.partitions": "8"}.

    Master và bộ nhớ không đặt ở đây mà do lệnh spark-submit trong image quyết định (--master local[4] ...),
    nên cùng một code chạy được local hay trên cluster.
    """
    b = (SparkSession.builder.appName(app)
         # Đặt UTC để kết quả ngày giờ giống nhau trên mọi máy
         .config("spark.sql.session.timeZone", "UTC")
         # Nơi lưu bảng khi dùng saveAsTable (step 07); không dùng thì không tạo gì
         .config("spark.sql.warehouse.dir", path("warehouse")))
    for k, v in (conf or {}).items():
        b = b.config(k, v)
    spark = b.getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    return spark


def section(title):
    """In tiêu đề để output của job chia thành từng mục dễ đọc (khớp với bảng mục trong doc)."""
    print(f"\n===== {title} =====", flush=True)


def dir_size_mb(p):
    """Tổng dung lượng các file trong thư mục (MB), dùng để so sánh định dạng/số file."""
    total = sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(p) for f in fs)
    return total / 1024 / 1024


def count_files(p):
    """Số file dữ liệu trong thư mục, bỏ file ẩn và file đánh dấu (_SUCCESS, .crc)."""
    return sum(1 for _, _, fs in os.walk(p) for f in fs if not f.startswith((".", "_")))


def hold():
    """HOLD=<giây> giữ driver sống để xem Spark UI (Spark UI tắt khi job kết thúc)."""
    secs = int(os.environ.get("HOLD", "0"))
    if secs:
        print(f"[hold] giữ {secs}s để xem Spark UI http://localhost:4040", flush=True)
        time.sleep(secs)
