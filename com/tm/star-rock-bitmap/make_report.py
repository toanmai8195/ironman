#!/usr/bin/env python3
"""Tổng hợp kết quả thô trong report/<limited|unlimited>/*.json thành:

  report/test1-tag-rows-vs-agg.md      Test 1: tag gold -> rows -> Mongo so với gold -> agg -> Mongo
  report/test2-tag-agg-vs-sr.md        Test 2: tag gold -> agg -> Mongo so với gold -> bitmap trong StarRocks
  report/test3-segment.md              Test 3: tính segment từ tag trong Mongo so với trong StarRocks
  report/test4-getall.md               Test 4: lấy toàn bộ user của segment từ Mongo so với từ StarRocks
  report/REPORT.md                     Report tổng và khuyến nghị (chèn thêm report/recommendation.md nếu có)

Chạy: python3 com/tm/star-rock-bitmap/make_report.py
"""
import json
from pathlib import Path

REPORT = Path(__file__).resolve().parent / "report"
MODES = [("limited", "Có giới hạn tài nguyên (StarRocks 6 CPU/8GB, Mongo 3 CPU/6GB, service 2 CPU/3GB)"),
         ("unlimited", "Không giới hạn (StarRocks, Mongo, service dùng tối đa 10 core, RAM không giới hạn)")]

TESTS = [
    dict(id="t1", file="test1-tag-rows-vs-agg.md", title="Test 1: tag compute, gold → rows → bitmap Mongo so với gold → agg → bitmap Mongo",
         desc="Đo từ lúc bắt đầu đọc gold đến lúc tag đã lưu xong trong Mongo (bitmap cắt thành chunk tối đa 8MB, tối đa 10 chunk ghi đồng thời).",
         unit="tag",
         cases=[("t1-rows", "A tag total: gold -> mongo", "gold → rows → bitmap → Mongo", "SR trả từng user, service build bitmap"),
                ("t1-agg", "A tag total: gold -> mongo", "gold → agg → bitmap → Mongo", "SR gom bitmap bằng bitmap_agg, service giải mã")]),
    dict(id="t2", file="test2-tag-agg-vs-sr.md", title="Test 2: tag compute, gold → agg → bitmap Mongo so với gold → bitmap trong StarRocks",
         desc="Đo từ lúc bắt đầu đọc gold đến lúc bitmap tag sẵn sàng (lưu xong trong Mongo, hoặc INSERT xong vào bảng bitmap của StarRocks).",
         unit="tag",
         cases=[("t2-agg", "A tag total: gold -> mongo", "gold → agg → bitmap → Mongo", "SR gom bitmap, service giải mã rồi ghi chunk Mongo"),
                ("t2-sr", "B tag total: gold -> sr", "gold → bitmap trong StarRocks", "INSERT ... SELECT bitmap_agg chạy hoàn toàn trong SR")]),
    dict(id="t3", file="test3-segment.md", title="Test 3: tính segment từ bitmap tag trong Mongo so với trong StarRocks",
         desc="Đo từ lúc bắt đầu lấy bitmap tag đến lúc segment đã lưu xong. Mỗi segment là and/or/not của 10 tag bất kỳ (segment 5 đến 10 triệu user); Mongo tối đa 10 chunk đọc song song.",
         unit="segment",
         cases=[("t3-mongo", "A total (fetch+compute+store)", "tag Mongo → segment Mongo", "tải 10 tag, and/or/not ở service, ghi segment"),
                ("t3-sr", "B total: SQL compute + store", "tag StarRocks → segment StarRocks", "một câu INSERT ... SELECT bitmap_and/or/andnot trong SR")]),
    dict(id="t4", file="test4-getall.md", title="Test 4: lấy toàn bộ user của segment từ Mongo so với từ StarRocks",
         desc="Đo từ lúc bắt đầu get đến lúc service có toàn bộ user của segment (5 đến 10 triệu user).",
         unit="lần get",
         cases=[("t4-mongo", "A get all users: mongo get chunks + iterate", "segment Mongo → service", "get chunk, giải mã, duyệt hết user"),
                ("t4-sr", "B get all users: SQL unnest", "segment StarRocks → service", "SELECT unnest(bitmap_to_array(bm)), trả từng hàng")]),
    dict(id="t5", file="test5-segment-hybrid.md", title="Test 5: segment chỉ Mongo so với kiến trúc lai (StarRocks tính segment, xuất sang Mongo)",
         desc="Đo từ lúc bắt đầu lấy dữ liệu (Mongo: get 10 tag; lai: bắt đầu query StarRocks) đến lúc segment đã lưu xong trong Mongo, sẵn sàng cho consumer lấy toàn bộ user.",
         unit="segment",
         cases=[("t5-mongo", "A total (fetch+compute+store)", "tag Mongo → segment Mongo (chỉ Mongo)", "tải 10 tag, and/or/not ở service, ghi chunk Mongo"),
                ("t5-hybrid", "B hybrid total: SR compute + export to mongo", "tag StarRocks → segment StarRocks → Mongo (lai)",
                 "SR tính và lưu segment, rồi bitmap_to_base64, giải mã, ghi chunk Mongo")]),
    dict(id="t6", file="test6-sr-vs-service-cache.md", title="Test 6: StarRocks tính và lấy toàn bộ user so với nạp tag vào cache của service rồi tính",
         desc="Đo từ lúc có yêu cầu đến lúc service có toàn bộ user của segment (100 segment, 5 đến 10 triệu user mỗi segment). "
              "t6-sr: StarRocks tính và lưu segment, rồi trả toàn bộ user về service. t6-cache: tag chỉ nằm trong StarRocks, được nạp lên cache của service "
              "(nạp lạnh toàn bộ tag đo riêng), service tính and/or/not trong bộ nhớ rồi duyệt hết user.",
         unit="segment",
         cases=[("t6-sr", "B e2e total: compute + store + get all users (SR)", "StarRocks tính + lưu, rồi lấy toàn bộ user",
                 "INSERT ... bitmap_and/or/andnot trong SR, rồi SELECT unnest toàn bộ"),
                ("t6-cache", "C segment total: compute + all users (cache)", "cache tag trong service, tính trong service",
                 "and/or/not trên bitmap tag đã nạp sẵn trong bộ nhớ, rồi duyệt hết user")],
         extra=[("t6-cache", "C1 cold load all tags (SR -> service cache)", "nạp lạnh toàn bộ 50 tag từ StarRocks vào cache"),
                ("t6-cache", "C0 load one tag (SR bitmap_to_base64 + decode)", "nạp một tag (bitmap_to_base64 + giải mã)")]),
    dict(id="t7", file="test7-load-segment.md", title="Test 7: nạp segment lên service (cache miss), một luồng: từ Mongo so với từ StarRocks",
         desc="Đo từ lúc bắt đầu nạp một segment đã lưu đến lúc service có bitmap trong bộ nhớ (như khi cache của service chưa có segment đó). "
              "2000 lần nạp, mỗi lần một segment ngẫu nhiên (5 đến 10 triệu user), tuần tự một luồng. Sau khi nạp xong hai cách giống hệt nhau (RoaringBitmap trong bộ nhớ).",
         unit="lần nạp",
         cases=[("t7-mongo", "A load segment: mongo get chunks + deserialize", "segment trong Mongo → service", "get chunk, giải mã"),
                ("t7-sr", "B load segment: SR bitmap_to_base64 + decode", "segment trong StarRocks → service", "SELECT bitmap_to_base64(bm), giải mã")]),
    dict(id="t8", file="test8-load-segment-parallel.md", title="Test 8: nạp segment lên service, 8 luồng cùng lúc: từ Mongo so với từ StarRocks",
         desc="Như test 7 nhưng 8 luồng nạp cùng lúc (mỗi luồng một connection StarRocks; Mongo tối đa 10 chunk đồng thời), để thấy khi nhiều request cùng cache miss thì bên nào chịu tải tốt hơn. "
              "Latency là của từng lần nạp; thông lượng là số lần nạp mỗi giây của cả case.",
         unit="lần nạp",
         cases=[("t8-mongo", "A load segment: mongo get chunks + deserialize", "segment trong Mongo → service (8 luồng)", "get chunk, giải mã"),
                ("t8-sr", "B load segment: SR bitmap_to_base64 + decode", "segment trong StarRocks → service (8 luồng)", "SELECT bitmap_to_base64(bm), giải mã")]),
    dict(id="t9", file="test9-contains-and-page.md", title="Test 9: check contains và lấy một trang 1000 user: trực tiếp trên StarRocks so với từ cache của service",
         desc="Hai thao tác đọc nhỏ trên một segment (working set 100 segment, 5 đến 10 triệu user mỗi segment, 2000 lần mỗi case). "
              "SR: một câu SQL mỗi lần trên bitmap trong StarRocks (`bitmap_contains`, hoặc `bitmap_subset_limit` + `unnest`). "
              "Cache: bitmap đã nạp sẵn trong bộ nhớ của service (cache hit), nên chi phí nạp lần đầu nằm ngoài các số latency (xem phần hoà vốn).",
         unit="lần",
         cases=[("t9-contains-sr", "B contains: SR bitmap_contains", "contains trực tiếp trên StarRocks (1 luồng)", "SELECT bitmap_contains(bm, user)"),
                ("t9-contains-cache", "C contains (cache hit)", "contains trên cache của service (1 luồng)", "bitmap.contains(user) trong bộ nhớ"),
                ("t9-page-sr", "B get 1000 users page: SR bitmap_subset_limit + unnest", "lấy 1000 user trực tiếp trên StarRocks (1 luồng)", "bitmap_subset_limit + unnest"),
                ("t9-page-cache", "C get 1000 users page (cache hit)", "lấy 1000 user trên cache của service (1 luồng)", "batch iterator trong bộ nhớ"),
                ("t9-contains-sr8", "B contains: SR bitmap_contains", "contains trực tiếp trên StarRocks (8 luồng)", "như trên, 8 luồng cùng lúc"),
                ("t9-page-sr8", "B get 1000 users page: SR bitmap_subset_limit + unnest", "lấy 1000 user trực tiếp trên StarRocks (8 luồng)", "như trên, 8 luồng cùng lúc")]),
]


def load(mode, case):
    return json.loads((REPORT / mode / f"{case}.json").read_text())


def f(x):
    return f"{x:,.0f}" if x >= 1000 else f"{x:.1f}"


def mb(gb):
    return gb * 1000


def check_lines(t, data):
    out = []
    if t["id"] == "t3":
        for m, _ in MODES:
            a = data[m]["t3-mongo"]["notes"]["segment_users_a"]
            b = data[m]["t3-sr"]["notes"]["segment_users_b"]
            n = data[m]["t3-mongo"]["steps"][t["cases"][0][1]]["n"]
            out.append(f"- {m}: tổng số user của {n} segment: Mongo {a:,}, StarRocks {b:,}, " + ("khớp nhau." if a == b else "LỆCH NHAU."))
    elif t["id"] == "t4":
        for m, _ in MODES:
            a = data[m]["t4-mongo"]["notes"]["users_read_a"]
            b = data[m]["t4-sr"]["notes"]["users_read_b"]
            out.append(f"- {m}: tổng số user đọc được: Mongo {a:,}, StarRocks {b:,}, " + ("khớp nhau." if a == b else "LỆCH NHAU."))
    elif t["id"] in ("t7", "t8"):
        for m, _ in MODES:
            a = data[m][t["cases"][0][0]]["notes"]["users_loaded_a"]
            b = data[m][t["cases"][1][0]]["notes"]["users_loaded_b"]
            out.append(f"- {m}: tổng user của các segment đã nạp: Mongo {a:,}, StarRocks {b:,}, " + ("khớp nhau." if a == b else "LỆCH NHAU."))
    elif t["id"] == "t6":
        for m, _ in MODES:
            a = data[m]["t6-sr"]["notes"]["segment_users_b"]
            b = data[m]["t6-cache"]["notes"]["segment_users_c"]
            out.append(f"- {m}: tổng user của 100 segment: StarRocks {a:,}, cache trong service {b:,}, " + ("khớp nhau." if a == b else "LỆCH NHAU."))
    elif t["id"] == "t5":
        for m, _ in MODES:
            a = data[m]["t5-mongo"]["notes"]["segment_users_a"]
            b = data[m]["t5-hybrid"]["notes"]["segment_users_b"]
            e = data[m]["t5-hybrid"]["notes"]["segment_exported_users"]
            out.append(f"- {m}: tổng user của segment: chỉ Mongo {a:,}, StarRocks {b:,}, bản xuất sang Mongo {e:,}, " + ("khớp nhau." if a == b == e else "LỆCH NHAU."))
    else:
        out.append("- Số user trong từng tag được in trong log lúc chạy (`report/<chế độ>/logs/`); gold giống nhau giữa các case.")
    return out


def takeaways(t, data):
    (c1, s1, n1, _), (c2, s2, n2, _) = t["cases"]
    out = []
    for m, _ in MODES:
        a = data[m][c1]["steps"][s1]
        b = data[m][c2]["steps"][s2]
        fast = c1 if a["p50_ms"] <= b["p50_ms"] else c2
        ratio = max(a["p50_ms"], b["p50_ms"]) / min(a["p50_ms"], b["p50_ms"])
        ra = mb(data[m][c1]["resources"]["service"]["net_rx_gb"]) / a["n"]
        rb = mb(data[m][c2]["resources"]["service"]["net_rx_gb"]) / b["n"]
        out.append(f"- {m}: p50 {c1} = {f(a['p50_ms'])}ms, {c2} = {f(b['p50_ms'])}ms; **{fast}** nhanh hơn khoảng {ratio:.1f} lần ở p50 "
                   f"(p99: {f(a['p99_ms'])}ms so với {f(b['p99_ms'])}ms). Service nhận {ra:.1f}MB so với {rb:.1f}MB mỗi {t['unit']}.")
    return out


def fm(x):
    return f"{x * 1000:.1f}µs" if x < 1 else f(x) + "ms"


def test9_md(t, data):
    out = [f"# {t['title']}", "", t["desc"], "", "## Kịch bản", "",
           "- Gold giống nhau cho mọi test; working set 100 segment, mỗi segment 5 đến 10 triệu user, mỗi case 2000 thao tác ngẫu nhiên (user hoặc vị trí bắt đầu trang ngẫu nhiên trong universe 50 triệu).",
           "- Cùng danh sách thao tác cho StarRocks và cache nên kết quả so sánh được (số lần contains đúng, số user trong trang).",
           "- Cache: toàn bộ 100 segment (khoảng 630MB) nạp sẵn trong bộ nhớ; nạp lần đầu tính riêng (bước C0), không nằm trong latency của cache hit.",
           "- Số đo của cache hit rất nhỏ (micro giây) nên gồm cả chi phí đo thời gian; đọc như thứ tự độ lớn.", ""]
    for m, label in MODES:
        out += [f"## {m}", "", f"*{label}*", "", "### Latency", "", "| Case | n | avg | p50 | p90 | p99 | max |", "|---|---|---|---|---|---|---|"]
        for cid, step, name, how in t["cases"]:
            s = data[m][cid]["steps"][step]
            out.append(f"| {cid}: {name} | {s['n']} | {fm(s['avg_ms'])} | {fm(s['p50_ms'])} | {fm(s['p90_ms'])} | {fm(s['p99_ms'])} | {fm(s['max_ms'])} |")
        out += ["", "### Thông lượng và tài nguyên", "", "| Case | thao tác mỗi giây | CPU StarRocks avg / max (core) | CPU service avg / max | RAM max service (GB) | StarRocks tx (MB) | service rx mỗi thao tác (KB) |", "|---|---|---|---|---|---|---|"]
        for cid, step, _, _ in t["cases"]:
            d = data[m][cid]
            nt = d["notes"]
            r = d["resources"]
            out.append(f"| {cid} | {nt['loads'] * 1000 / nt['wall_ms']:,.0f} | {r['sr']['cpu_avg']:.2f} / {r['sr']['cpu_max']:.2f} | {r['service']['cpu_avg']:.2f} / {r['service']['cpu_max']:.2f} | "
                       f"{r['service']['mem_max_gb']:.2f} | {mb(r['sr']['net_tx_gb']):,.1f} | {r['service']['net_rx_gb'] * 1e6 / nt['loads']:.1f} |")
        ld = data[m]["t9-contains-cache"]["steps"]["C0 load segment (SR bitmap_to_base64 + decode)"]
        out += ["", f"Nạp 100 segment vào cache (một lần, ms mỗi segment): avg {f(ld['avg_ms'])}, p50 {f(ld['p50_ms'])}, p90 {f(ld['p90_ms'])}, p99 {f(ld['p99_ms'])}.", ""]
        out += ["### Hoà vốn của việc cache", "",
                "Số lần dùng một segment trong lúc nó còn nằm trong cache để việc nạp (một lần) rẻ hơn gọi thẳng StarRocks mỗi lần: n = chi phí nạp / (latency StarRocks mỗi lần trừ latency cache hit).", "",
                "| Thao tác | chi phí nạp (ms) | StarRocks mỗi lần (ms, avg) | cache hit (ms, avg) | hoà vốn n |", "|---|---|---|---|---|"]
        for lab, sr_case, sr_step, ca_case, ca_step in (("contains", "t9-contains-sr", "B contains: SR bitmap_contains", "t9-contains-cache", "C contains (cache hit)"),
                                                         ("lấy 1000 user", "t9-page-sr", "B get 1000 users page: SR bitmap_subset_limit + unnest", "t9-page-cache", "C get 1000 users page (cache hit)")):
            sr_ms = data[m][sr_case]["steps"][sr_step]["avg_ms"]
            ca_ms = data[m][ca_case]["steps"][ca_step]["avg_ms"]
            out.append(f"| {lab} | {ld['avg_ms']:.1f} | {sr_ms:.2f} | {ca_ms:.4f} | {ld['avg_ms'] / (sr_ms - ca_ms):.1f} |")
        out += [""]
    out += ["## Kiểm tra tính đúng", ""]
    for m, _ in MODES:
        a = data[m]["t9-contains-sr"]["notes"]["contains_true"]
        b = data[m]["t9-contains-cache"]["notes"]["contains_true"]
        c = data[m]["t9-page-sr"]["notes"]["page_users"]
        d = data[m]["t9-page-cache"]["notes"]["page_users"]
        out.append(f"- {m}: contains đúng: StarRocks {a:,}, cache {b:,}, " + ("khớp nhau" if a == b else "LỆCH NHAU") + f"; user trong trang: StarRocks {c:,}, cache {d:,}, " + ("khớp nhau." if c == d else "LỆCH NHAU."))
    out += ["", "## So sánh có giới hạn và không giới hạn (p50, avg của StarRocks trực tiếp)", "", "| Case | có giới hạn | không giới hạn | thay đổi |", "|---|---|---|---|"]
    for cid, step, _, _ in t["cases"]:
        x = data["limited"][cid]["steps"][step]["p50_ms"]
        y = data["unlimited"][cid]["steps"][step]["p50_ms"]
        out.append(f"| {cid} | {fm(x)} | {fm(y)} | {(y / x - 1) * 100:+.0f}% |")
    return "\n".join(out) + "\n"


def test_md(t, data):
    if t["id"] == "t9":
        return test9_md(t, data)
    n_label = t["unit"]
    first = t["cases"][0]
    n = data["limited"][first[0]]["steps"][first[1]]["n"]
    out = [f"# {t['title']}", "", t["desc"], "", "## Kịch bản", "",
           "- Gold giống nhau cho mọi test: 50 tag, 10 attribute, universe 50 triệu user, mỗi tag 5 đến 10 triệu user.",
           f"- Số lần đo mỗi case: {n} {n_label}. Mỗi case chạy một lần cho mỗi chế độ, trong container service riêng.",
           "- Mongo: bitmap lưu thành chunk tối đa 8MB, tối đa 10 chunk đọc hoặc ghi đồng thời. StarRocks: bitmap native.",
           "- CPU (core), RAM, network lấy từ `docker stats` mỗi 1 đến 2 giây trong lúc case chạy. Network là tổng của cả case, kèm mỗi lần đo.", ""]
    for m, label in MODES:
        out += [f"## {m}", "", f"*{label}*", "", "### Latency (ms)", "",
                "| Case | Mô tả | n | avg | p50 | p90 | p99 | min | max |", "|---|---|---|---|---|---|---|---|---|"]
        for cid, step, name, how in t["cases"]:
            s = data[m][cid]["steps"][step]
            out.append(f"| {cid} | {name}: {how} | {s['n']} | {f(s['avg_ms'])} | {f(s['p50_ms'])} | {f(s['p90_ms'])} | {f(s['p99_ms'])} | {f(s['min_ms'])} | {f(s['max_ms'])} |")
        if t.get("extra"):
            out += ["", "Chi phí nạp cache (ms):", "", "| Mô tả | n | avg | p50 | p90 | p99 |", "|---|---|---|---|---|---|"]
            for cid, step, lab in t["extra"]:
                s = data[m][cid]["steps"][step]
                out.append(f"| {lab} | {s['n']} | {f(s['avg_ms'])} | {f(s['p50_ms'])} | {f(s['p90_ms'])} | {f(s['p99_ms'])} |")
        if t["id"] in ("t7", "t8"):
            out += ["", "Thông lượng (cả case):", "", "| Case | số lần nạp | thời gian (ms) | lần nạp mỗi giây |", "|---|---|---|---|"]
            for cid, *_ in t["cases"]:
                nt = data[m][cid]["notes"]
                out.append(f"| {cid} | {nt['loads']} | {nt['wall_ms']:,} | {nt['loads'] * 1000 / nt['wall_ms']:.1f} |")
        out += ["", "### Network và tài nguyên", "",
                f"| Case | service rx (MB) | service tx (MB) | Mongo tx (MB) | SR tx (MB) | service rx mỗi {n_label} (MB) | service tx mỗi {n_label} (MB) |",
                "|---|---|---|---|---|---|---|"]
        for cid, step, _, _ in t["cases"]:
            d = data[m][cid]
            k = d["steps"][step]["n"]
            r = d["resources"]
            out.append(f"| {cid} | {mb(r['service']['net_rx_gb']):,.0f} | {mb(r['service']['net_tx_gb']):,.0f} | {mb(r['mongo']['net_tx_gb']):,.0f} | "
                       f"{mb(r['sr']['net_tx_gb']):,.0f} | {mb(r['service']['net_rx_gb']) / k:.1f} | {mb(r['service']['net_tx_gb']) / k:.1f} |")
        out += ["", "| Case | CPU service avg / max (core) | CPU Mongo avg / max | CPU StarRocks avg / max | RAM max service / Mongo / StarRocks (GB) | thời gian chạy (s) |",
                "|---|---|---|---|---|---|"]
        for cid, step, _, _ in t["cases"]:
            d = data[m][cid]
            r = d["resources"]
            out.append(f"| {cid} | {r['service']['cpu_avg']:.2f} / {r['service']['cpu_max']:.2f} | {r['mongo']['cpu_avg']:.2f} / {r['mongo']['cpu_max']:.2f} | "
                       f"{r['sr']['cpu_avg']:.2f} / {r['sr']['cpu_max']:.2f} | {r['service']['mem_max_gb']:.1f} / {r['mongo']['mem_max_gb']:.1f} / {r['sr']['mem_max_gb']:.1f} | {d['wall_seconds']:.0f} |")
        out += [""]
        for cid, step, _, _ in t["cases"]:
            subs = [k for k in data[m][cid]["steps"] if k != step]
            if subs:
                out += [f"Các bước con của {cid} (ms):", "", "| bước | n | avg | p50 | p90 | p99 |", "|---|---|---|---|---|---|"]
                for k in subs:
                    s = data[m][cid]["steps"][k]
                    out.append(f"| {k} | {s['n']} | {f(s['avg_ms'])} | {f(s['p50_ms'])} | {f(s['p90_ms'])} | {f(s['p99_ms'])} |")
                out += [""]
    out += ["## So sánh có giới hạn và không giới hạn (ms)", "", "| Case | chỉ số | có giới hạn | không giới hạn | thay đổi |", "|---|---|---|---|---|"]
    for cid, step, _, _ in t["cases"]:
        for key, lab in (("avg_ms", "avg"), ("p50_ms", "p50"), ("p90_ms", "p90"), ("p99_ms", "p99")):
            x = data["limited"][cid]["steps"][step][key]
            y = data["unlimited"][cid]["steps"][step][key]
            out.append(f"| {cid} | {lab} | {f(x)} | {f(y)} | {(y / x - 1) * 100:+.0f}% |")
    out += ["", "## Kiểm tra tính đúng", ""] + check_lines(t, data) + ["", "## Nhận xét", ""] + takeaways(t, data) + [""]
    return "\n".join(out)


def main():
    data = {m: {} for m, _ in MODES}
    for t in TESTS:
        for cid, *_ in t["cases"]:
            for m, _ in MODES:
                data[m][cid] = load(m, cid)
    for t in TESTS:
        (REPORT / t["file"]).write_text(test_md(t, data))
    out = ["# Báo cáo tổng: Mongo và StarRocks cho bài toán segmentation", "",
           "Report từng test: " + ", ".join(f"[{t['file']}]({t['file']})" for t in TESTS) + ". Số liệu thô: `report/limited/` và `report/unlimited/`.", "",
           "## Kịch bản chung", "",
           "- Gold: 50 tag, 10 attribute, universe 50 triệu user, mỗi tag 5 đến 10 triệu user, cùng bảng gold cho mọi test.",
           "- Segment: 300 segment, mỗi segment là and/or/not của 10 tag bất kỳ (seed 42), kết quả 5 đến 10 triệu user; cùng các segment cho Mongo và StarRocks.",
           "- Mongo: bitmap lưu thành chunk tối đa 8MB, tối đa 10 chunk đọc hoặc ghi đồng thời. StarRocks: bitmap native.",
           "- Hai chế độ: có giới hạn (StarRocks 6 CPU/8GB, Mongo 3 CPU/6GB, service 2 CPU/3GB) và không giới hạn.", ""]
    for key, ttl in (("p50_ms", "p50"), ("p90_ms", "p90"), ("p99_ms", "p99"), ("avg_ms", "avg")):
        out += [f"## Latency {ttl} (ms)", "", "| Test | Case | có giới hạn | không giới hạn |", "|---|---|---|---|"]
        for t in TESTS:
            for cid, step, name, _ in t["cases"]:
                out.append(f"| {t['id'][1]} | {cid}: {name} | {f(data['limited'][cid]['steps'][step][key])} | {f(data['unlimited'][cid]['steps'][step][key])} |")
        out += [""]
    out += ["## Network mỗi lần đo và tài nguyên (có giới hạn)", "",
            "| Test | Case | service rx mỗi lần (MB) | service tx mỗi lần (MB) | CPU service avg (core) | CPU StarRocks avg | CPU Mongo avg | RAM max StarRocks (GB) |", "|---|---|---|---|---|---|---|---|"]
    for t in TESTS:
        for cid, step, name, _ in t["cases"]:
            d = data["limited"][cid]
            k = d["steps"][step]["n"]
            r = d["resources"]
            out.append(f"| {t['id'][1]} | {cid} | {mb(r['service']['net_rx_gb']) / k:.1f} | {mb(r['service']['net_tx_gb']) / k:.1f} | "
                       f"{r['service']['cpu_avg']:.2f} | {r['sr']['cpu_avg']:.2f} | {r['mongo']['cpu_avg']:.2f} | {r['sr']['mem_max_gb']:.1f} |")
    out += [""]
    rec = REPORT / "recommendation.md"
    out += [rec.read_text() if rec.exists() else "## Khuyến nghị\n\n(chưa có)\n", ""]
    (REPORT / "REPORT.md").write_text("\n".join(out))
    print("đã ghi", ", ".join(t["file"] for t in TESTS), "và REPORT.md")


if __name__ == "__main__":
    main()
