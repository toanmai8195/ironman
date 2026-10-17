#!/usr/bin/env bash
# Chạy toàn bộ benchmark tuần tự và cùng kịch bản: load gold, Mongo rows, Mongo agg, StarRocks.
# Dùng: com/tm/star-rock-bitmap/run_all.sh [thư-mục-log]   (chạy từ thư mục gốc repo)
# Cần: docker compose --profile bitmap đã up (xem README), jar đã copy vào com/tm/docker/ironman/bitmap/bench.jar,
# và (tuỳ chọn) python3 com/tm/docker/ironman/bitmap/docker_stats_exporter.py để có CPU/RAM/network theo container.
set -euo pipefail
OUT=${1:-/tmp/star-rock-bitmap-run}; mkdir -p "$OUT"
F=com/tm/docker/ironman/docker-compose.yml
SR='jdbc:mysql://starrocks-bitmap:9030/?sessionVariables=query_timeout=7200'; MG=mongodb://mongo-bitmap:27017
COMMON="--tags 30 --tags-per-attribute 5 --universe 50000000 --segments 600 --reads 4000 --seed 42 --sr $SR --mongo $MG"
run() { docker compose -f $F --profile bench run --rm --no-deps --service-ports --name ironman-bench-bitmap bench-bitmap "$@"; }
run load $COMMON > "$OUT/load.log" 2>&1
for v in "a rows" "a agg" "b agg"; do set -- $v
  echo "start $1-$2 $(date +%s)" >> "$OUT/progress"
  run run $COMMON --pipeline $1 --export $2 > "$OUT/$1-$2.log" 2>&1
  echo "end $1-$2 $(date +%s)" >> "$OUT/progress"
done
echo ALLDONE >> "$OUT/progress"
