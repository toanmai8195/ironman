#!/usr/bin/env bash
# Chạy các job PySpark trong container (local mode). Dùng: ./run.sh {step <n>|all|shell|sql|clean|list}
#   CORES=4 MEM=3g ./run.sh step 0     # đổi tài nguyên (mặc định 4 core / 3GB)
#   HOLD=120 ./run.sh step 0           # giữ job sau khi xong N giây để xem Spark UI http://localhost:4040
set -euo pipefail
cd "$(dirname "$0")"

IMAGE=${SPARK_IMAGE:-apache/spark:3.5.3-python3}
CORES=${CORES:-4}
MEM=${MEM:-3g}
mkdir -p data

run() {  # run <lệnh trong container...>
  docker run --rm -i${TTY:+t} --user root --cpus "$CORES" -p 4040:4040 \
    -v "$PWD/jobs:/jobs:ro" -v "$PWD/data:/data" \
    -e DATA_DIR=/data -e HOLD="${HOLD:-0}" -e PYTHONUNBUFFERED=1 \
    "$IMAGE" "$@"
}

submit() {
  echo "===== $1 ====="
  run /opt/spark/bin/spark-submit --master "local[$CORES]" --driver-memory "$MEM" \
    --conf spark.ui.showConsoleProgress=false \
    --conf spark.driver.extraJavaOptions=-Dlog4j.rootCategory=WARN,console \
    "/jobs/$(basename "$1")"
}

case "${1:-}" in
  step)  f=$(ls jobs/"$(printf '%02d' "$2")"_*.py | head -1); submit "$f" ;;
  all)   for f in jobs/[0-9][0-9]_*.py; do submit "$f"; done ;;
  shell) TTY=1 run /opt/spark/bin/pyspark --master "local[$CORES]" --driver-memory "$MEM" ;;
  sql)   TTY=1 run /opt/spark/bin/spark-sql --master "local[$CORES]" --driver-memory "$MEM" ;;
  clean) rm -rf data/* ;;
  list)  ls jobs ;;
  *)     echo "usage: $0 {step <n>|all|shell|sql|clean|list}"; exit 1 ;;
esac
