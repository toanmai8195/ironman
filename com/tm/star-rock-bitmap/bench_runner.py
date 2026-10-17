#!/usr/bin/env python3
"""Chạy 4 test của star-rock-bitmap, mỗi test hai chế độ (limited, unlimited).

  Test 1: tag gold -> rows -> bitmap Mongo  so với  gold -> agg -> bitmap Mongo      (tới khi lưu xong tag trong Mongo)
  Test 2: tag gold -> agg -> bitmap Mongo   so với  gold -> bitmap trong StarRocks   (tới khi bitmap sẵn sàng)
  Test 3: segment từ tag trong Mongo        so với  segment từ tag trong StarRocks   (tới khi lưu xong segment)
  Test 4: lấy toàn bộ user của segment từ Mongo so với từ StarRocks                  (tới khi service có đủ user)
  Test 5: segment chỉ Mongo (tag Mongo -> segment Mongo) so với kiến trúc lai (SR tính segment rồi xuất sang Mongo)

Cùng gold cho mọi test (50 tag, mỗi tag 5 đến 10 triệu user). Bitmap trong Mongo lưu thành chunk tối đa 8MB,
tối đa 10 chunk đọc hoặc ghi đồng thời.

Thứ tự trong một chế độ (tiết kiệm chi phí, vẫn mỗi test chạy đủ các case):
  1. reset data, load gold, test 1 (t1-rows, t1-agg), xoá data
  2. reset data, load gold, test 2 (t2-agg, t2-sr), rồi test 3 (t3-mongo, t3-sr) và test 4 (t4-mongo, t4-sr) trên cùng data, xoá data
  3. reset data, load gold, dựng tag trong Mongo và StarRocks (không tính vào test), test 5 (t5-mongo, t5-hybrid)

Dùng (từ thư mục gốc repo):
  python3 com/tm/star-rock-bitmap/bench_runner.py --mode limited      # giới hạn docker hiện tại
  python3 com/tm/star-rock-bitmap/bench_runner.py --mode unlimited    # bỏ giới hạn StarRocks, Mongo, service
  python3 com/tm/star-rock-bitmap/make_report.py                      # report từng test và report tổng

Cần: bench.jar đã copy vào com/tm/docker/ironman/bitmap/ (xem README). Kết quả thô: com/tm/star-rock-bitmap/report/<mode>/.
CPU, RAM, network lấy từ `docker stats` (lấy mẫu trong từng case), CPU tính theo core (1.0 = 1 core).
"""
import argparse
import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
COMPOSE = ROOT / "com/tm/docker/ironman/docker-compose.yml"
CONTAINERS = {"sr": "ironman-starrocks-bitmap", "mongo": "ironman-mongo-bitmap", "service": "ironman-bench-bitmap"}
INFRA = ["starrocks-bitmap", "mongo-bitmap", "mongo-exporter-bitmap", "prometheus-bitmap", "grafana-bitmap"]
VOLUMES = ["ironman_starrocks-bitmap-data", "ironman_mongo-bitmap-data"]
SR_URL = "jdbc:mysql://starrocks-bitmap:9030/?sessionVariables=query_timeout=7200"
MONGO_URL = "mongodb://mongo-bitmap:27017"

UNITS = {"B": 1, "KiB": 1024, "MiB": 1024**2, "GiB": 1024**3, "kB": 1e3, "MB": 1e6, "GB": 1e9, "TB": 1e12}

LIMITS = {
    "limited": {},  # mặc định trong compose: SR 6 CPU/8GB, Mongo 3 CPU/6GB, service 2 CPU/3GB
    "unlimited": {"SR_CPUS": "10", "SR_MEM": "0", "MONGO_CPUS": "10", "MONGO_MEM": "0", "BENCH_CPUS": "10", "BENCH_MEM": "0"},
}

def to_bytes(s):
    m = re.match(r"([\d.]+)\s*([A-Za-z]+)", s.strip())
    return float(m.group(1)) * UNITS[m.group(2)] if m else 0.0


def sh(cmd, env=None, check=True, capture=False):
    e = dict(os.environ)
    e.update(env or {})
    return subprocess.run(cmd, cwd=ROOT, env=e, check=check, text=True, capture_output=capture)


def compose(args, env=None, check=True):
    return sh(["docker", "compose", "-f", str(COMPOSE), "--profile", "bitmap", "--profile", "bench"] + args, env, check)


class Sampler(threading.Thread):
    """Lấy mẫu docker stats cho 3 container; tính CPU avg/max, RAM max, network delta (xử lý counter bị reset)."""

    def __init__(self):
        super().__init__(daemon=True)
        self.stop_flag = threading.Event()
        self.samples = {k: [] for k in CONTAINERS}  # key -> [(t, cpu_cores, mem_bytes, rx, tx)]

    def run(self):
        while not self.stop_flag.is_set():
            try:
                out = subprocess.run(["docker", "stats", "--no-stream", "--format", "{{json .}}"],
                                     capture_output=True, text=True, timeout=30).stdout
                now = time.time()
                for ln in out.splitlines():
                    c = json.loads(ln)
                    for k, name in CONTAINERS.items():
                        if c["Name"] == name:
                            rx, tx = (to_bytes(x) for x in c["NetIO"].split("/"))
                            self.samples[k].append((now, float(c["CPUPerc"].rstrip("%")) / 100,
                                                    to_bytes(c["MemUsage"].split("/")[0]), rx, tx))
            except Exception as e:  # docker tạm lỗi thì bỏ qua mẫu này
                print("sampler lỗi:", e, file=sys.stderr)
            self.stop_flag.wait(0.3)

    def summary(self):
        out = {}
        for k, s in self.samples.items():
            if not s:
                out[k] = None
                continue
            cpu = [x[1] for x in s]
            rx = tx = 0.0
            prev = (0.0, 0.0)
            for _, _, _, r, t in s:  # container mới tạo thì bắt đầu từ 0; counter giảm nghĩa là reset
                rx += r - prev[0] if r >= prev[0] else r
                tx += t - prev[1] if t >= prev[1] else t
                prev = (r, t)
            out[k] = {"cpu_avg": sum(cpu) / len(cpu), "cpu_max": max(cpu), "mem_max_gb": max(x[2] for x in s) / 2**30,
                      "net_rx_gb": rx / 1e9, "net_tx_gb": tx / 1e9, "samples": len(s)}
        return out


def baseline_counters():
    """Counter network hiện tại của container bền (SR, Mongo) trước khi chạy bước, để trừ đi phần cũ."""
    out = subprocess.run(["docker", "stats", "--no-stream", "--format", "{{json .}}"], capture_output=True, text=True).stdout
    base = {}
    for ln in out.splitlines():
        c = json.loads(ln)
        for k in ("sr", "mongo"):
            if c["Name"] == CONTAINERS[k]:
                rx, tx = (to_bytes(x) for x in c["NetIO"].split("/"))
                base[k] = (rx, tx)
    return base


def wait_healthy(timeout=600):
    t0 = time.time()
    for name in (CONTAINERS["sr"], CONTAINERS["mongo"]):
        while True:
            r = sh(["docker", "inspect", "-f", "{{.State.Health.Status}}", name], check=False, capture=True)
            if r.stdout.strip() == "healthy":
                break
            if time.time() - t0 > timeout:
                raise RuntimeError(f"{name} không healthy sau {timeout}s")
            time.sleep(5)
    time.sleep(10)


def reset_infra(env):
    """Xoá toàn bộ data StarRocks và Mongo (volume), dựng lại với giới hạn của chế độ đang chạy."""
    print("== reset infra (xoá data SR + Mongo)", flush=True)
    sh(["docker", "rm", "-f", CONTAINERS["service"]], check=False, capture=True)
    compose(["rm", "-sf", "starrocks-bitmap", "mongo-bitmap", "mongo-exporter-bitmap"], env, check=False)
    sh(["docker", "volume", "rm"] + VOLUMES, check=False, capture=True)
    compose(["up", "-d", "--no-deps"] + INFRA, env)
    wait_healthy()
    for k in ("sr", "mongo"):
        r = sh(["docker", "inspect", "-f", "cpus={{.HostConfig.NanoCpus}} mem={{.HostConfig.Memory}}", CONTAINERS[k]], capture=True)
        print(f"   {k}: {r.stdout.strip()}", flush=True)


def common_args(a):
    return ["--tags", "50", "--tags-per-attribute", "5", "--universe", str(a.universe), "--min-pct", "10", "--max-pct", "20",
            "--seg-min", "0.105", "--seg-max", "0.195", "--segments", str(a.segments), "--full-gets", str(a.full_gets),
            "--chunk-bytes", "8000000", "--seed", "42", "--sr", SR_URL, "--mongo", MONGO_URL]


def run_case(a, outdir, env, test, case, cmd, pipeline, export="agg", extra=None):
    """Chạy 1 case trong container service, lấy mẫu tài nguyên, ghi <case>.json (kết quả bench + resources)."""
    jpath = outdir / f"{case}.json"
    logpath = outdir / "logs" / f"{case}.log"
    logpath.parent.mkdir(parents=True, exist_ok=True)
    out_name = a.outname or a.mode
    args = [cmd] + common_args(a) + ["--pipeline", pipeline, "--export", export, "--test", test, "--limits", a.mode,
                                     "--case", case, "--out", f"/out/{out_name}/{case}.json"] + (extra or [])
    print(f"== {case}: {cmd} --pipeline {pipeline} --export {export}", flush=True)
    sh(["docker", "rm", "-f", CONTAINERS["service"]], check=False, capture=True)
    base = baseline_counters()
    sampler = Sampler()
    sampler.start()
    t0 = time.time()
    with open(logpath, "w") as lf:
        r = subprocess.run(
            ["docker", "compose", "-f", str(COMPOSE), "--profile", "bitmap", "--profile", "bench", "run", "--rm", "--no-deps",
             "--service-ports", "--name", CONTAINERS["service"], "bench-bitmap"] + args,
            cwd=ROOT, env={**os.environ, **env}, stdout=lf, stderr=subprocess.STDOUT)
    wall = time.time() - t0
    sampler.stop_flag.set()
    sampler.join(timeout=60)
    if r.returncode != 0:
        raise RuntimeError(f"{case} lỗi (exit {r.returncode}), xem {logpath}")
    data = json.loads(jpath.read_text())
    summ = sampler.summary()
    for k in ("sr", "mongo"):  # trừ counter network cũ của container bền
        s = sampler.samples[k]
        if s and k in base:
            rx = tx = 0.0
            prev = base[k]
            for _, _, _, rr, tt in s:
                rx += rr - prev[0] if rr >= prev[0] else rr
                tx += tt - prev[1] if tt >= prev[1] else tt
                prev = (rr, tt)
            summ[k]["net_rx_gb"], summ[k]["net_tx_gb"] = rx / 1e9, tx / 1e9
    data["resources"] = summ
    data["wall_seconds"] = round(wall, 1)
    data["case"] = case
    data["test"] = test
    data["limits"] = a.mode
    jpath.write_text(json.dumps(data, indent=1, ensure_ascii=False))
    return data


def load_gold(a, outdir, env):
    sh(["docker", "rm", "-f", CONTAINERS["service"]], check=False, capture=True)
    (outdir / "logs").mkdir(parents=True, exist_ok=True)
    print("== load gold", flush=True)
    with open(outdir / "logs" / "load.log", "a") as lf:
        subprocess.run(["docker", "compose", "-f", str(COMPOSE), "--profile", "bitmap", "--profile", "bench", "run", "--rm", "--no-deps",
                        "--service-ports", "--name", CONTAINERS["service"], "bench-bitmap", "load"] + common_args(a)
                       + ["--test", "load", "--limits", a.mode, "--case", "load"],
                       cwd=ROOT, env={**os.environ, **env}, stdout=lf, stderr=subprocess.STDOUT, check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["limited", "unlimited"], required=True)
    ap.add_argument("--tests", default="t1,t234,t5", help="t1, t234 (test 2, 3, 4 chạy liền trên cùng data), t5")
    ap.add_argument("--segments", type=int, default=300)
    ap.add_argument("--full-gets", type=int, default=40)
    ap.add_argument("--universe", type=int, default=50000000)
    ap.add_argument("--outname", default=None, help="thư mục kết quả trong report/ (mặc định: tên mode)")
    a = ap.parse_args()
    env = LIMITS[a.mode]
    outdir = HERE / "report" / (a.outname or a.mode)
    outdir.mkdir(parents=True, exist_ok=True)
    log = lambda m: print(time.strftime("%H:%M:%S"), m, flush=True)
    for g in a.tests.split(","):
        reset_infra(env)
        load_gold(a, outdir, env)
        if g == "t1":
            run_case(a, outdir, env, "t1", "t1-rows", "etl", "a", "rows")
            run_case(a, outdir, env, "t1", "t1-agg", "etl", "a", "agg")
        elif g == "t234":
            run_case(a, outdir, env, "t2", "t2-agg", "etl", "a", "agg")
            run_case(a, outdir, env, "t2", "t2-sr", "etl", "b")
            run_case(a, outdir, env, "t3", "t3-mongo", "segment", "a")
            run_case(a, outdir, env, "t3", "t3-sr", "segment", "b")
            run_case(a, outdir, env, "t4", "t4-mongo", "getall", "a")
            run_case(a, outdir, env, "t4", "t4-sr", "getall", "b")
        elif g == "t5":
            # chuẩn bị (không tính vào test): tag trong Mongo (agg) và trong StarRocks
            run_case(a, outdir, env, "setup", "setup-tag-mongo", "etl", "a", "agg")
            run_case(a, outdir, env, "setup", "setup-tag-sr", "etl", "b")
            run_case(a, outdir, env, "t5", "t5-mongo", "segment", "a")
            run_case(a, outdir, env, "t5", "t5-hybrid", "segment", "b", extra=["--export-to-mongo", "true"])
        else:
            raise SystemExit(f"nhóm không hợp lệ: {g}")
        log(f"xong {g}")
    reset_infra(env)  # xoá data cuối cùng
    (outdir / "DONE").write_text(time.strftime("%Y-%m-%d %H:%M:%S"))
    log("ALLDONE")


if __name__ == "__main__":
    main()
