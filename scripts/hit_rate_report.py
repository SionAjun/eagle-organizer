import json
from pathlib import Path
from collections import defaultdict

TAGS = json.load(open("config/tags.json", encoding="utf-8"))
THRESHOLD_MIN_SCOPE = 50

rows = []
for prefix, tag_list in TAGS["tags"].items():
    prefix_key = prefix + "-"
    for tag_obj in tag_list:
        name = tag_obj["name"]
        hit = tag_obj.get("hit_count", 0)
        scope = tag_obj.get("scope_count", 0)
        rate = hit / scope if scope > 0 else 0.0
        if scope < THRESHOLD_MIN_SCOPE:
            verdict = "数据不足"
        elif rate < 0.01:
            verdict = "真冷门(可删)"
        elif rate < 0.05:
            verdict = "灰区(观望)"
        else:
            verdict = "健康"
        rows.append((prefix_key, name, hit, scope, rate, verdict))

rows.sort(key=lambda r: (r[0], -r[4]))

with open("reports/hit_rate_v24_step5.md", "w", encoding="utf-8") as f:
    f.write("# 命中率裁决报告 v2.4 / Step 5\n\n")
    f.write(f"门槛: scope ≥ {THRESHOLD_MIN_SCOPE} 才进入裁决\n\n")

    by_prefix = defaultdict(list)
    for r in rows:
        by_prefix[r[0]].append(r)

    f.write("## 前缀级汇总\n\n")
    f.write("| 前缀 | 标签数 | 健康 | 灰区 | 真冷门 | 数据不足 |\n")
    f.write("|---|---|---|---|---|---|\n")
    for prefix in sorted(by_prefix.keys()):
        prs = by_prefix[prefix]
        c = {"健康": 0, "灰区(观望)": 0, "真冷门(可删)": 0, "数据不足": 0}
        for _, _, _, _, _, v in prs:
            c[v] += 1
        f.write(f"| {prefix} | {len(prs)} | {c['健康']} | {c['灰区(观望)']} | {c['真冷门(可删)']} | {c['数据不足']} |\n")

    for prefix in sorted(by_prefix.keys()):
        f.write(f"\n## {prefix}\n\n")
        f.write("| 标签 | hit | scope | 条件命中率 | 状态 |\n")
        f.write("|---|---|---|---|---|\n")
        for _, name, hit, scope, rate, verdict in by_prefix[prefix]:
            f.write(f"| {name} | {hit} | {scope} | {rate*100:.2f}% | {verdict} |\n")

print("Done -> reports/hit_rate_v24_step5.md")
