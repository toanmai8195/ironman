#!/usr/bin/env python3
"""Xuất CPU, RAM và network (tích luỹ rx/tx) từng container (docker stats) cho Prometheus, port 9465.

CPU của starrocks_be_cpu là của cả VM Docker nên lẫn Mongo; cái này đo riêng từng container.
Chạy trên host: python3 docker_stats_exporter.py  (Prometheus scrape host.docker.internal:9465)
"""
import json
import re
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

UNITS = {"B": 1, "KiB": 1024, "MiB": 1024**2, "GiB": 1024**3, "kB": 1000, "MB": 1000**2, "GB": 1000**3}
state = ""


def to_bytes(s):
    m = re.match(r"([\d.]+)\s*([A-Za-z]+)", s.strip())
    return float(m.group(1)) * UNITS[m.group(2)] if m else 0.0


def poll():
    global state
    while True:
        try:
            out = subprocess.run(
                ["docker", "stats", "--no-stream", "--format", "{{json .}}"],
                capture_output=True, text=True, timeout=30).stdout
            lines = []
            for ln in out.splitlines():
                c = json.loads(ln)
                name = c["Name"]
                if "bitmap" not in name:
                    continue
                cpu = float(c["CPUPerc"].rstrip("%")) / 100  # 1.0 = 1 core
                mem = to_bytes(c["MemUsage"].split("/")[0])
                rx, tx = (to_bytes(x.strip()) for x in c["NetIO"].split("/"))
                lines.append(f'container_net_rx_bytes_total{{container="{name}"}} {rx}')
                lines.append(f'container_net_tx_bytes_total{{container="{name}"}} {tx}')
                lines.append(f'container_cpu_cores{{container="{name}"}} {cpu}')
                lines.append(f'container_mem_bytes{{container="{name}"}} {mem}')
            state = "\n".join(lines) + "\n"
        except Exception as e:  # giữ exporter sống khi docker tạm lỗi
            print("poll lỗi:", e)
        time.sleep(1)


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        body = state.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


threading.Thread(target=poll, daemon=True).start()
HTTPServer(("0.0.0.0", 9465), H).serve_forever()
