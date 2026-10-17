#!/usr/bin/env python3
"""Sinh dashboard Grafana bitmap-bench: mỗi test một row, có latency (avg, p50, p90, p99), CPU, RAM,
network, operation của StarRocks, MongoDB, service. Biến `limits` chọn chế độ chạy (limited hoặc unlimited).

Chạy: python3 com/tm/docker/ironman/bitmap/make_dashboard.py
"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent / "grafana/provisioning/dashboards/bitmap-bench.json"
DS = {"type": "prometheus"}
CONT = 'container=~"ironman-(starrocks|mongo|bench)-bitmap"'
RANGE = "[12h]"

TESTS = [
    ("t1", "Test 1: tag compute, gold → rows → bitmap Mongo so với gold → agg → bitmap Mongo",
     "Latency từ khi bắt đầu đọc gold đến khi tag đã lưu xong trong Mongo (các chunk tối đa 8MB, tối đa 10 chunk ghi đồng thời). "
     "t1-rows: SR trả từng user, service build bitmap. t1-agg: SR gom bitmap (bitmap_agg), service giải mã.",
     "(A|B) tag total.*", "tag"),
    ("t2", "Test 2: tag compute, gold → agg → bitmap Mongo so với gold → bitmap trong StarRocks",
     "Latency từ khi bắt đầu đọc gold đến khi bitmap tag sẵn sàng. t2-agg: lưu vào Mongo. t2-sr: INSERT ... bitmap_agg vào bảng bitmap của StarRocks.",
     "(A|B) tag total.*", "tag"),
    ("t3", "Test 3: tính segment từ bitmap tag trong Mongo so với trong StarRocks",
     "Latency từ khi bắt đầu lấy bitmap tag (Mongo: get 10 tag, tối đa 10 chunk đọc song song; SR: bắt đầu query) đến khi segment lưu xong "
     "(and/or/not của 10 tag bất kỳ, segment 5 đến 10 triệu user).",
     "(A total.*|B total.*)", "segment"),
    ("t4", "Test 4: lấy toàn bộ user của segment từ Mongo so với từ StarRocks",
     "Latency từ khi bắt đầu get đến khi service có toàn bộ user của segment. Mongo: get chunk, giải mã, duyệt hết. SR: SELECT unnest(bitmap_to_array(bm)) trả từng hàng.",
     "(A get all.*|B get all.*)", "get"),
]


def tgt(expr, legend, ref="A", instant=False, fmt=None):
    t = {"expr": expr, "legendFormat": legend, "refId": ref}
    if instant:
        t["instant"] = True
    if fmt:
        t["format"] = fmt
    return t


def ts(pid, title, desc, targets, x, y, w, h, unit="short", decimals=None):
    d = {"unit": unit}
    if decimals is not None:
        d["decimals"] = decimals
    return {"id": pid, "type": "timeseries", "title": title, "description": desc, "datasource": DS,
            "gridPos": {"x": x, "y": y, "w": w, "h": h}, "fieldConfig": {"defaults": d, "overrides": []}, "targets": targets,
            "options": {"legend": {"displayMode": "table", "placement": "right", "calcs": ["mean", "max"]}}}


def main():
    panels = []
    pid = 1
    y = 0
    for tid, title, desc, step_re, kind in TESTS:
        sel = f'test="{tid}",limits="$limits"'
        main_sel = f'{sel},step=~"{step_re}"'
        win = f'and on() max(bench_phase_active{{{sel}}})'
        panels.append({"id": pid, "type": "row", "title": title, "collapsed": False, "gridPos": {"x": 0, "y": y, "w": 24, "h": 1}, "panels": []})
        pid += 1
        y += 1
        # bảng latency avg, p50, p90, p99 theo case
        qs = [f'max by (case) (last_over_time(bench_latency_ms_sum{{{main_sel}}}{RANGE})/last_over_time(bench_latency_ms_count{{{main_sel}}}{RANGE}))']
        for q in ("0.5", "0.9", "0.99"):
            qs.append(f'max by (case) (last_over_time(bench_latency_ms_quantile{{{main_sel},quantile="{q}"}}{RANGE}))')
        qs.append(f'max by (case) (last_over_time(bench_latency_ms_count{{{main_sel}}}{RANGE}))')
        panels.append({
            "id": pid, "type": "table", "title": f"Latency: avg, p50, p90, p99 (ms) — {desc.split('.')[0]}", "description": desc,
            "datasource": DS, "gridPos": {"x": 0, "y": y, "w": 24, "h": 6},
            "fieldConfig": {"defaults": {"unit": "ms", "decimals": 1}, "overrides": [{"matcher": {"id": "byName", "options": "n"}, "properties": [{"id": "unit", "value": "short"}, {"id": "decimals", "value": 0}]}]},
            "options": {"showHeader": True},
            "targets": [tgt(e, "", chr(65 + k), True, "table") for k, e in enumerate(qs)],
            "transformations": [{"id": "merge", "options": {}},
                                {"id": "organize", "options": {"excludeByName": {"Time": True},
                                                               "renameByName": {"case": "Case", "Value #A": "avg", "Value #B": "p50", "Value #C": "p90", "Value #D": "p99", "Value #E": "n"},
                                                               "indexByName": {"case": 0, "Value #A": 1, "Value #B": 2, "Value #C": 3, "Value #D": 4, "Value #E": 5}}}]})
        pid += 1
        y += 6
        # latency theo thời gian: avg, p50, p90, p99 của từng case
        lat = [tgt(f'sum by (case) (bench_latency_ms_sum{{{main_sel}}})/sum by (case) (bench_latency_ms_count{{{main_sel}}})', "{{case}} avg", "A")]
        for k, q in enumerate(("0.5", "0.9", "0.99")):
            lat.append(tgt(f'max by (case) (bench_latency_ms_quantile{{{main_sel},quantile="{q}"}})', "{{case}} p" + str(int(float(q) * 100)), chr(66 + k)))
        has_sub = tid != "t4"  # test 4 chỉ có một bước, không có bước con
        panels.append(ts(pid, "Latency theo thời gian: avg, p50, p90, p99 (ms)",
                         "Số tích luỹ từ đầu case đến thời điểm đó (avg và phân vị của mọi lần đo tới lúc này).", lat, 0, y, 12 if has_sub else 24, 8, "ms", 1))
        pid += 1
        if has_sub:
            panels.append(ts(pid, "Latency trung bình từng bước (ms)",
                             "Trung bình từng bước con của mỗi case (ví dụ A1 SR -> bitmap, A3 ghi chunk Mongo, A4 tải chunk, A5 tính, B1 INSERT trong SR).",
                             [tgt(f'sum by (case, step) (bench_latency_ms_sum{{{sel},step!~"{step_re}"}})/sum by (case, step) (bench_latency_ms_count{{{sel},step!~"{step_re}"}})', "{{case}} · {{step}}")],
                             12, y, 12, 8, "ms", 1))
            pid += 1
        y += 8
        panels.append(ts(pid, "CPU theo container (core)", "CPU thực dùng của StarRocks, MongoDB và service benchmark trong lúc test chạy (docker stats; 1 = 1 core).",
                         [tgt(f'container_cpu_cores{{{CONT}}} {win}', "{{container}}")], 0, y, 12, 8, "short", 2))
        pid += 1
        panels.append(ts(pid, "RAM theo container", "RAM thực dùng của StarRocks, MongoDB và service benchmark trong lúc test chạy (docker stats).",
                         [tgt(f'container_mem_bytes{{{CONT}}} {win}', "{{container}}")], 12, y, 12, 8, "bytes"))
        pid += 1
        y += 8
        panels.append(ts(pid, "Network nhận theo container (byte/s)", "Lưu lượng mạng vào từng container trong lúc test chạy.",
                         [tgt(f'rate(container_net_rx_bytes_total{{{CONT}}}[10s]) {win}', "{{container}}")], 0, y, 12, 8, "Bps"))
        pid += 1
        panels.append(ts(pid, "Network gửi theo container (byte/s)", "Lưu lượng mạng ra từ từng container trong lúc test chạy.",
                         [tgt(f'rate(container_net_tx_bytes_total{{{CONT}}}[10s]) {win}', "{{container}}")], 12, y, 12, 8, "Bps"))
        pid += 1
        y += 8
        panels.append(ts(pid, "StarRocks: query/s", "Số câu query FE StarRocks nhận mỗi giây trong lúc test chạy.",
                         [tgt(f'rate(starrocks_fe_query_total[10s]) {win}', "qps")], 0, y, 8, 7, "short", 2))
        pid += 1
        panels.append(ts(pid, "MongoDB: operation/s", "Số thao tác Mongo mỗi giây theo loại (insert, query, update, getmore, delete) trong lúc test chạy.",
                         [tgt(f'sum by (legacy_op_type) (rate(mongodb_ss_opcounters{{legacy_op_type=~"insert|query|update|getmore|delete"}}[10s])) {win}', "{{legacy_op_type}}")], 8, y, 8, 7, "short", 1))
        pid += 1
        panels.append(ts(pid, "Service: lượt đo/s", "Số lần thao tác chính (một tag, một segment hoặc một lần get) service hoàn thành mỗi giây.",
                         [tgt(f'sum by (case) (rate(bench_latency_ms_count{{{main_sel}}}[10s]))', "{{case}}")], 16, y, 8, 7, "short", 2))
        pid += 1
        y += 7
    dash = {
        "title": "star-rock-bitmap benchmark", "uid": "bitmap-bench", "schemaVersion": 39, "refresh": "5s",
        "time": {"from": "now-3h", "to": "now"}, "panels": panels,
        "templating": {"list": [{"name": "limits", "label": "Chế độ", "type": "custom", "query": "limited,unlimited",
                                 "current": {"selected": True, "text": "limited", "value": "limited"},
                                 "options": [{"selected": True, "text": "limited", "value": "limited"},
                                             {"selected": False, "text": "unlimited", "value": "unlimited"}],
                                 "includeAll": False, "multi": False}]},
    }
    OUT.write_text(json.dumps(dash, indent=1, ensure_ascii=False))
    print("đã ghi", OUT, len(panels), "panel")


if __name__ == "__main__":
    main()
