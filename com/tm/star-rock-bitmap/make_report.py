#!/usr/bin/env python3
"""Tổng hợp các report từng bước trong report/<limited|unlimited>/*.json thành report/REPORT.md.

Chạy: python3 com/tm/star-rock-bitmap/make_report.py
"""
import json
import re
from pathlib import Path

REPORT = Path(__file__).resolve().parent / "report"
MODES = [("limited", "Có giới hạn (SR 6 CPU/8GB, Mongo 3 CPU/6GB, service 2 CPU/3GB)"),
         ("unlimited", "Không giới hạn (SR, Mongo, service dùng tối đa 10 core, RAM không giới hạn)")]

# (mã bài toán, file, tên bước chính, nhãn, đơn vị trên mỗi thao tác)
CASES = [
    ("1.1", "1.1-tag-mongo-rows", "A tag total: gold -> mongo", "Mongo rows (đọc gold rows, lưu Mongo)", "tag"),
    ("1.2", "1.2-tag-mongo-agg-g1", "A tag total: gold -> mongo", "Mongo agg (đọc gold agg bitmap, lưu Mongo)", "tag"),
    ("1.3", "1.3-tag-sr", "B tag total: gold -> sr", "StarRocks (gold -> bitmap tag trong SR)", "tag"),
    ("2.1", "2.1-segment-mongo", "A total (fetch+compute+store)", "Mongo (get 10 tag, and/or/not, ghi Mongo)", "segment"),
    ("2.2", "2.2-segment-sr", "B total: SQL compute + store", "StarRocks (tính và lưu trong SR)", "segment"),
    ("3.1", "3.1-getall-mongo", "A get all users: mongo get + iterate", "Mongo (get blob + duyệt hết user)", "lần get"),
    ("3.2", "3.2-getall-sr", "B get all users: SQL unnest", "StarRocks (SELECT unnest toàn bộ)", "lần get"),
]
PROBLEMS = [("1", "Bài 1. Thời gian từ đọc gold đến có bitmap tag (mỗi tag 5 đến 10 triệu user)", ["1.1", "1.2", "1.3"]),
            ("2", "Bài 2. Thời gian tính segment đến khi segment sẵn sàng (segment 5 đến 10 triệu user)", ["2.1", "2.2"]),
            ("3", "Bài 3. Thời gian lấy toàn bộ user của segment", ["3.1", "3.2"])]


def load(mode, f):
    return json.loads((REPORT / mode / f"{f}.json").read_text())


def fmt(x):
    return f"{x:,.0f}" if x >= 1000 else f"{x:.1f}"


def main():
    data = {m: {c[0]: load(m, c[1]) for c in CASES} for m, _ in MODES}
    out = ["# Báo cáo benchmark bitmap: Mongo vs StarRocks", ""]
    # kịch bản
    lg = (REPORT / "limited" / "logs")
    tags = [int(x) for x in re.findall(r"card=(\d+)", (lg / "1.1-tag-mongo-rows.log").read_text())]
    segs = [int(x) for x in re.findall(r"card A=(\d+)", (lg / "2.1-segment-mongo.log").read_text())]
    a = data["limited"]["3.1"]["notes"]["users_read_a"]
    b = data["limited"]["3.2"]["notes"]["users_read_b"]
    out += ["## Kịch bản", "",
            f"- Gold: 30 tag, 6 attribute, universe 50 triệu user. Mỗi tag {min(tags) / 1e6:.2f} đến {max(tags) / 1e6:.2f} triệu user (trung bình {sum(tags) / len(tags) / 1e6:.2f} triệu).",
            f"- Segment: {len(segs)} segment, mỗi segment là biểu thức AND/OR/AND NOT trên 10 tag ngẫu nhiên (seed 42), kết quả {min(segs) / 1e6:.2f} đến {max(segs) / 1e6:.2f} triệu user. Cùng các segment cho mọi pipeline.",
            "- Lấy toàn bộ user: 40 segment mẫu ngẫu nhiên (cùng mẫu cho Mongo và StarRocks). "
            f"Tổng user đọc được: Mongo {a:,}, StarRocks {b:,}, " + ("khớp nhau." if a == b else "LỆCH NHAU."),
            "- Mỗi lúc chỉ xử lý một tag (bài 1) hoặc một segment (bài 2); tạo xong cả 30 tag mới sang segment. Mongo tối đa 10 lần get đồng thời (mỗi blob nhỏ hơn 1 chunk 8MB).",
            "- Mỗi bước chạy một lần trong container service riêng; thứ tự: nhóm 1 (1.1, 1.2), nhóm 2 (1.2, 2.1, 3.1), nhóm 3 (1.3, 2.2, 3.2); xoá hết data giữa các nhóm.",
            "- Thời gian đo bằng benchmark (avg, p50, p90, p99, ms). CPU (core), RAM và network lấy từ `docker stats` lấy mẫu trong từng bước.",
            ""]
    for m, lab in MODES:
        out += [f"- **{m}**: {lab}"]
    out += [""]
    # kích thước blob Mongo (bitmap roaring) của tag và segment
    tb = [float(x) for x in re.findall(r"blob=([\d.]+)MB", (lg / "1.1-tag-mongo-rows.log").read_text())]
    sb = [float(x) for x in re.findall(r"blob=([\d.]+)MB", (lg / "2.1-segment-mongo.log").read_text())]
    out += [f"- Kích thước bitmap roaring lưu trong Mongo: tag {min(tb):.1f}MB và segment {max(sb):.1f}MB (log chỉ ghi 1 chữ số thập phân; mọi blob đều bằng nhau ở mức này). Tag và segment 5 đến 10 triệu user trên universe 50 triệu đủ dày để roaring dùng bitmap container, nên mọi blob đều gần bằng kích thước tối đa của universe (50 triệu bit, khoảng 6,3MB).", ""]
    P = lambda m, c: data[m][c]["steps"][next(x for x in CASES if x[0] == c)[2]]["p50_ms"]
    out += ["## Kết luận nhanh (p50, ms; số có giới hạn / không giới hạn)", "",
            f"- Bài 1: Mongo rows {fmt(P('limited', '1.1'))} / {fmt(P('unlimited', '1.1'))}, Mongo agg {fmt(P('limited', '1.2'))} / {fmt(P('unlimited', '1.2'))}, StarRocks {fmt(P('limited', '1.3'))} / {fmt(P('unlimited', '1.3'))}. Mongo rows chậm hơn khoảng {P('limited', '1.1') / P('limited', '1.2'):.1f} lần so với agg vì phải kéo từng user về service; StarRocks và Mongo agg gần ngang nhau.",
            f"- Bài 2: Mongo {fmt(P('limited', '2.1'))} / {fmt(P('unlimited', '2.1'))}, StarRocks {fmt(P('limited', '2.2'))} / {fmt(P('unlimited', '2.2'))}. Hai bên gần ngang nhau; StarRocks ít biến động hơn ở p90 khi có giới hạn. Mongo phải tải khoảng {data['limited']['2.1']['resources']['service']['net_rx_gb'] * 1000 / 300:.0f}MB mỗi segment, StarRocks gần như không có network ra service.",
            f"- Bài 3: Mongo {fmt(P('limited', '3.1'))} / {fmt(P('unlimited', '3.1'))}, StarRocks {fmt(P('limited', '3.2'))} / {fmt(P('unlimited', '3.2'))}. Mongo nhanh hơn khoảng {P('limited', '3.2') / P('limited', '3.1'):.0f} lần: Mongo trả một blob nén khoảng {data['limited']['3.1']['resources']['service']['net_rx_gb'] * 1000 / 40:.1f}MB, còn StarRocks trả từng user dạng hàng, khoảng {data['limited']['3.2']['resources']['service']['net_rx_gb'] * 1000 / 40:.0f}MB mỗi lần.",
            "- Bỏ giới hạn tài nguyên dường như chỉ cải thiện bước tag ở 1.2 và 1.3 (khoảng 20 đến 24%, nhưng 1.2 tự dao động khoảng 14% giữa hai lần chạy nên con số này chưa chắc chắn); bài 2 và bài 3 gần như không đổi, nên giới hạn hiện tại không có vẻ là nút thắt của chúng.",
            ""]
    for pid, title, ids in PROBLEMS:
        out += [f"## {title}", ""]
        for m, lab in MODES:
            out += [f"### {m}", "", "| Trường hợp | n | avg (ms) | p50 | p90 | p99 | min | max |", "|---|---|---|---|---|---|---|---|"]
            for cid in ids:
                c = next(x for x in CASES if x[0] == cid)
                s = data[m][cid]["steps"][c[2]]
                out.append(f"| {cid} {c[3]} | {s['n']} | {fmt(s['avg_ms'])} | {fmt(s['p50_ms'])} | {fmt(s['p90_ms'])} | {fmt(s['p99_ms'])} | {fmt(s['min_ms'])} | {fmt(s['max_ms'])} |")
            out += [""]
            out += ["Network và tài nguyên (docker stats): network là tổng MB trong bước và MB mỗi thao tác; service = container chạy benchmark.", "",
                    "| Trường hợp | service rx | service tx | Mongo tx | SR tx | rx service mỗi thao tác (MB) | CPU service avg/max (core) | CPU Mongo avg/max | CPU SR avg/max | RAM max service / Mongo / SR (GB) |",
                    "|---|---|---|---|---|---|---|---|---|---|"]
            for cid in ids:
                c = next(x for x in CASES if x[0] == cid)
                d = data[m][cid]
                n = d["steps"][c[2]]["n"]
                r = d["resources"]
                sv, mg, sr = r["service"], r["mongo"], r["sr"]
                out.append(f"| {cid} | {sv['net_rx_gb'] * 1000:,.0f} | {sv['net_tx_gb'] * 1000:,.0f} | {mg['net_tx_gb'] * 1000:,.0f} | {sr['net_tx_gb'] * 1000:,.0f} | "
                           f"{sv['net_rx_gb'] * 1000 / n:.1f} | {sv['cpu_avg']:.2f} / {sv['cpu_max']:.2f} | {mg['cpu_avg']:.2f} / {mg['cpu_max']:.2f} | "
                           f"{sr['cpu_avg']:.2f} / {sr['cpu_max']:.2f} | {sv['mem_max_gb']:.1f} / {mg['mem_max_gb']:.1f} / {sr['mem_max_gb']:.1f} |")
            out += [""]
        # so sánh limited và unlimited của bước chính
        out += ["### So sánh có giới hạn và không giới hạn (p50, ms)", "", "| Trường hợp | có giới hạn | không giới hạn | thay đổi |", "|---|---|---|---|"]
        for cid in ids:
            c = next(x for x in CASES if x[0] == cid)
            x = data["limited"][cid]["steps"][c[2]]["p50_ms"]
            y = data["unlimited"][cid]["steps"][c[2]]["p50_ms"]
            out.append(f"| {cid} {c[3]} | {fmt(x)} | {fmt(y)} | {(y / x - 1) * 100:+.0f}% |")
        out += [""]
    # lặp lại 1.2 để kiểm tra độ ổn định
    out += ["## Độ ổn định: bài 1.2 chạy hai lần (nhóm 1 và nhóm 2), p50 ms", "", "| chế độ | nhóm 1 | nhóm 2 |", "|---|---|---|"]
    for m, _ in MODES:
        g1 = load(m, "1.2-tag-mongo-agg-g1")["steps"]["A tag total: gold -> mongo"]["p50_ms"]
        g2 = load(m, "1.2-tag-mongo-agg-g2")["steps"]["A tag total: gold -> mongo"]["p50_ms"]
        out.append(f"| {m} | {fmt(g1)} | {fmt(g2)} |")
    out += ["", "## Lưu ý về độ tin cậy", "",
            "- Mỗi bước chạy một lần cho mỗi chế độ, nên chênh lệch nhỏ (dưới khoảng 15%, xem độ ổn định của 1.2 ở trên) có thể là nhiễu giữa các lần chạy.",
            "- CPU, RAM, network lấy từ `docker stats` mỗi 1 đến 2 giây. Với bước ngắn (bài 1.2 và 1.3 chỉ khoảng 8 đến 12 giây) chỉ có vài mẫu, nên CPU max và RAM max thô hơn; network của docker stats có độ phân giải khoảng MB.",
            "- Network của container Mongo, SR là tổng lưu lượng mọi kết nối của container đó (kể cả exporter Prometheus, rất nhỏ). Ở chế độ không giới hạn, các container tranh chung 10 core và RAM của Docker với nhau, nhưng các bước chạy tuần tự nên không chạy đồng thời.",
            "- Compute của StarRocks (bài 2.2) là cả câu SQL gồm tính và ghi; không tách riêng được tính toán và ghi. Với Mongo, 2.1 gồm tải 10 tag, tính, serialize và ghi.",
            "- Size bitmap trên StarRocks không được đo trong lượt này.",
            "", "## Chi tiết các bước con", "", "Xem `report/<chế độ>/report-g1.md`, `report-g2.md`, `report-g3.md` (từng bước con như A1 đến A7, B1) và các file `.json` kèm log trong `logs/`.", ""]
    (REPORT / "REPORT.md").write_text("\n".join(out))
    print("đã ghi", REPORT / "REPORT.md")


if __name__ == "__main__":
    main()
