#!/usr/bin/env python3
"""Chạy 3 bài toán đo của star-rock-bitmap theo từng nhóm, mỗi bước có report riêng, xoá data giữa các nhóm.

  1. Tạo bitmap tag từ gold (mỗi tag 5 đến 10 triệu user): 1.1 Mongo rows, 1.2 Mongo agg, 1.3 StarRocks
  2. Tạo segment (kết quả 5 đến 10 triệu user): 2.1 Mongo (get 10 tag, and/or/not, ghi Mongo), 2.2 StarRocks
  3. Lấy toàn bộ user của segment: 3.1 Mongo, 3.2 StarRocks

Nhóm (cách chạy 2):
  g1: load gold, 1.1, 1.2                      -> report nhóm, xoá data
  g2: load gold, 1.2, 2.1, 3.1                 -> report nhóm, xoá data
  g3: load gold, 1.3, 2.2, 3.2                 -> report nhóm, xoá data

Dùng (từ thư mục gốc repo):
  python3 com/tm/star-rock-bitmap/bench_runner.py --mode limited      # giới hạn docker hiện tại
  python3 com/tm/star-rock-bitmap/bench_runner.py --mode unlimited    # bỏ giới hạn StarRocks, Mongo, service

Cần: bench.jar đã copy vào com/tm/docker/ironman/bitmap/ (xem README). Kết quả: com/tm/star-rock-bitmap/report/<mode>/.
CPU, RAM, network lấy từ `docker stats` (lấy mẫu mỗi ~1,5s trong từng bước), CPU tính theo core (1.0 = 1 core).
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

# bước chính của từng bài toán
MAIN_STEP = {
    "1.1": "A tag total: gold -> mongo",
    "1.2": "A tag total: gold -> mongo",
    "1.3": "B tag total: gold -> sr",
    "2.1": "A total (fetch+compute+store)",
    "2.2": "B total: SQL compute + store",
    "3.1": "A get all users: mongo get + iterate",
    "3.2": "B get all users: SQL unnest",
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
    return ["--tags", "30", "--tags-per-attribute", "5", "--universe", str(a.universe), "--min-pct", "10", "--max-pct", "20", "--seg-min", "0.105", "--seg-max", "0.195",
            "--segments", str(a.segments), "--full-gets", str(a.full_gets), "--reads", "0", "--seed", "42",
            "--sr", SR_URL, "--mongo", MONGO_URL]


def run_phase(a, outdir, env, key, cmd, pipeline, export="agg"):
    """Chạy 1 bước trong container service, lấy mẫu tài nguyên, ghi <key>.json (kết quả bench + resources)."""
    name = f"{key}"
    jpath = outdir / f"{name}.json"
    logpath = outdir / "logs" / f"{name}.log"
    logpath.parent.mkdir(parents=True, exist_ok=True)
    args = [cmd] + common_args(a) + ["--pipeline", pipeline, "--export", export, "--out", f"/out/{a.outname or a.mode}/{name}.json"]
    print(f"== {key}: {cmd} --pipeline {pipeline} --export {export}", flush=True)
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
        raise RuntimeError(f"{key} lỗi (exit {r.returncode}), xem {logpath}")
    data = json.loads(jpath.read_text())
    summ = sampler.summary()
    # trừ counter network cũ của container bền
    for k in ("sr", "mongo"):
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
    data["key"] = key
    jpath.write_text(json.dumps(data, indent=1, ensure_ascii=False))
    return data


def phase_md(title, data, main_step, n_label):
    st = data["steps"][main_step]
    n = st["n"]
    res = data["resources"]
    rows = [f"### {title}", "",
            f"Bước đo: `{main_step}`, n = {n} {n_label}, thời gian chạy {data['wall_seconds']}s", "",
            "| avg | p50 | p90 | p99 | min | max |", "|---|---|---|---|---|---|",
            f"| {st['avg_ms']:.1f} | {st['p50_ms']:.1f} | {st['p90_ms']:.1f} | {st['p99_ms']:.1f} | {st['min_ms']:.1f} | {st['max_ms']:.1f} |", "",
            "Tài nguyên và network trong bước (docker stats):", "",
            "| container | CPU avg (core) | CPU max | RAM max (GB) | network rx (MB) | network tx (MB) | rx mỗi " + n_label + " (MB) | tx mỗi " + n_label + " (MB) |",
            "|---|---|---|---|---|---|---|---|"]
    for k, lab in (("service", "service"), ("mongo", "mongo"), ("sr", "starrocks")):
        r = res.get(k)
        if r:
            rows.append(f"| {lab} | {r['cpu_avg']:.2f} | {r['cpu_max']:.2f} | {r['mem_max_gb']:.2f} | {r['net_rx_gb'] * 1000:.0f} | {r['net_tx_gb'] * 1000:.0f} | "
                        f"{r['net_rx_gb'] * 1000 / n:.1f} | {r['net_tx_gb'] * 1000 / n:.1f} |")
    other = [k for k in data["steps"] if k != main_step]
    if other:
        rows += ["", "Các bước con (ms):", "", "| bước | n | avg | p50 | p90 | p99 |", "|---|---|---|---|---|---|"]
        for k in other:
            s = data["steps"][k]
            rows.append(f"| {k} | {s['n']} | {s['avg_ms']:.1f} | {s['p50_ms']:.1f} | {s['p90_ms']:.1f} | {s['p99_ms']:.1f} |")
    rows.append("")
    return "\n".join(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["limited", "unlimited"], required=True)
    ap.add_argument("--groups", default="g1,g2,g3")
    ap.add_argument("--segments", type=int, default=300)
    ap.add_argument("--full-gets", type=int, default=40)
    ap.add_argument("--universe", type=int, default=50000000)
    ap.add_argument("--outname", default=None, help="thư mục kết quả trong report/ (mặc định: tên mode)")
    a = ap.parse_args()
    env = LIMITS[a.mode]
    outdir = HERE / "report" / (a.outname or a.mode)
    outdir.mkdir(parents=True, exist_ok=True)
    groups = a.groups.split(",")
    log = lambda m: print(time.strftime("%H:%M:%S"), m, flush=True)

    def load(env):
        sh(["docker", "rm", "-f", CONTAINERS["service"]], check=False, capture=True)
        with open(outdir / "logs" / "load.log", "a") as lf:
            log("load gold")
            subprocess.run(["docker", "compose", "-f", str(COMPOSE), "--profile", "bitmap", "--profile", "bench", "run", "--rm", "--no-deps",
                            "--service-ports", "--name", CONTAINERS["service"], "bench-bitmap", "load"] + common_args(a),
                           cwd=ROOT, env={**os.environ, **env}, stdout=lf, stderr=subprocess.STDOUT, check=True)

    (outdir / "logs").mkdir(parents=True, exist_ok=True)
    for g in groups:
        reset_infra(env)
        load(env)
        md = [f"## Nhóm {g} ({a.mode})", ""]
        if g == "g1":
            d11 = run_phase(a, outdir, env, "1.1-tag-mongo-rows", "etl", "a", "rows")
            d12 = run_phase(a, outdir, env, "1.2-tag-mongo-agg-g1", "etl", "a", "agg")
            md += [phase_md("1.1 Mongo rows: đọc gold rows, lưu Mongo", d11, MAIN_STEP["1.1"], "tag"),
                   phase_md("1.2 Mongo agg: đọc gold agg bitmap, lưu Mongo", d12, MAIN_STEP["1.2"], "tag")]
        elif g == "g2":
            d12 = run_phase(a, outdir, env, "1.2-tag-mongo-agg-g2", "etl", "a", "agg")
            d21 = run_phase(a, outdir, env, "2.1-segment-mongo", "segment", "a")
            d31 = run_phase(a, outdir, env, "3.1-getall-mongo", "getall", "a")
            md += [phase_md("1.2 Mongo agg (lần 2, để có tag trong Mongo)", d12, MAIN_STEP["1.2"], "tag"),
                   phase_md("2.1 Segment trên Mongo: get 10 tag, and/or/not, ghi Mongo", d21, MAIN_STEP["2.1"], "segment"),
                   phase_md("3.1 Lấy toàn bộ user của segment từ Mongo", d31, MAIN_STEP["3.1"], "lần get")]
        elif g == "g3":
            d13 = run_phase(a, outdir, env, "1.3-tag-sr", "etl", "b")
            d22 = run_phase(a, outdir, env, "2.2-segment-sr", "segment", "b")
            d32 = run_phase(a, outdir, env, "3.2-getall-sr", "getall", "b")
            md += [phase_md("1.3 StarRocks: đọc gold, tính bitmap tag, lưu bảng bitmap", d13, MAIN_STEP["1.3"], "tag"),
                   phase_md("2.2 Segment trên StarRocks: tính và lưu segment", d22, MAIN_STEP["2.2"], "segment"),
                   phase_md("3.2 Lấy toàn bộ user của segment từ StarRocks", d32, MAIN_STEP["3.2"], "lần get")]
        (outdir / f"report-{g}.md").write_text("\n".join(md))
        log(f"xong nhóm {g}, report: {outdir}/report-{g}.md")
    reset_infra(env)  # xoá data cuối cùng
    (outdir / "DONE").write_text(time.strftime("%Y-%m-%d %H:%M:%S"))
    log("ALLDONE")


if __name__ == "__main__":
    main()
