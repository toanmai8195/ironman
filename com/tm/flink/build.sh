#!/usr/bin/env bash
# Build fat jar của job Flink và đặt vào com/tm/flink/dist/ (compose mount thư mục này vào /opt/flink/usrlib).
set -euo pipefail
cd "$(dirname "$0")/../../.."
bazel build //com/tm/flink:cdc_flatten_deploy.jar
mkdir -p com/tm/flink/dist
install -m 0644 bazel-bin/com/tm/flink/cdc_flatten_deploy.jar com/tm/flink/dist/cdc-flatten.jar
echo "đã tạo com/tm/flink/dist/cdc-flatten.jar"
