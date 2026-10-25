"""Macro spark_job: mỗi job PySpark là một bộ target riêng <name>_py / <name>_tar / <name>_image / <name>_docker.

Layout trong image (giống layout thư mục trong repo, bỏ tiền tố com/tm/spark):
  /opt/app/jobs/<job>.py            job (chỉ đóng job của target này)
  /opt/app/lib/...                  các py_library trong deps, nằm trên PYTHONPATH
  /opt/app/conf/log4j2.properties   cấu hình log
"""

load("@rules_oci//oci:defs.bzl", "oci_image", "oci_load")
load("@rules_python//python:defs.bzl", "py_library")
load("@tar.bzl", "mutate", "tar")

_PKG = "com/tm/spark"
_DEFAULT_DEPS = ["//com/tm/spark/lib:common"]
_CONF = ["//com/tm/spark/conf:log4j2"]

def spark_job(name, src, deps = _DEFAULT_DEPS, tag_version = "v1.0.0"):
    """Image chạy đúng một job (Spark local mode).

    Args:
      name: tên job, thành tên target và tên image (com.tm.spark.<name>:<tag_version>).
      src: file job, vd "jobs/01_generate_data.py".
      deps: các py_library job import (mặc định //com/tm/spark/lib:common). Mỗi lib được đóng vào /opt/app/lib.
      tag_version: tag image.
    """
    job_file = src.split("/")[-1]

    # Khai báo job và phụ thuộc của nó trong đồ thị Bazel (Bazel kiểm tra deps tồn tại, đổi lib thì image tự build lại).
    py_library(
        name = name + "_py",
        srcs = [src],
        deps = deps,
    )

    # Đóng job + lib + conf vào một layer. Đường dẫn trong tar lấy theo vị trí file trong repo,
    # strip_prefix bỏ "com/tm/spark" và package_dir thêm "opt/app" => /opt/app/jobs/..., /opt/app/lib/...
    # (py_library chỉ xuất file srcs của chính nó, nên lib phải liệt kê trong deps của job; lib lồng lib thì thêm vào deps luôn.)
    tar(
        name = name + "_tar",
        srcs = [":" + name + "_py"] + deps + _CONF,
        out = name + "_layer.tar",
        mutate = mutate(strip_prefix = _PKG, package_dir = "opt/app"),
    )

    oci_image(
        name = name + "_image",
        base = "@spark_base",
        entrypoint = ["/opt/spark/bin/spark-submit"],
        # cmd là phần mặc định, ghi đè được khi docker run (vd đổi --master local[8] --driver-memory 6g)
        cmd = [
            "--master",
            "local[4]",
            "--driver-memory",
            "3g",
            "--conf",
            "spark.ui.showConsoleProgress=false",
            "--conf",
            "spark.driver.extraJavaOptions=-Dlog4j.configurationFile=file:///opt/app/conf/log4j2.properties",
            "/opt/app/jobs/" + job_file,
        ],
        env = {
            "DATA_DIR": "/data",
            "PYTHONPATH": "/opt/app/lib",
            "PYTHONUNBUFFERED": "1",
        },
        tars = [":" + name + "_tar"],
        user = "root",  # ghi được vào volume /data (Docker volume ironman-spark-data)
        visibility = ["//visibility:public"],
    )

    oci_load(
        name = name + "_docker",
        image = ":" + name + "_image",
        repo_tags = ["com.tm.spark.%s:%s" % (name, tag_version)],
        visibility = ["//visibility:public"],
    )
