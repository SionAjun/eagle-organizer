"""
扫描 progress.json，找出含废弃标签的 item，生成 review_queue.md。
只读不写 Eagle。
"""
import json
from pathlib import Path
from collections import defaultdict

BASE_DIR      = Path(__file__).parent
PROGRESS_FILE = BASE_DIR / "progress.json"
PENDING_FILE  = BASE_DIR / "pending.json"
OUTPUT_FILE   = BASE_DIR / "review_queue.md"

# 废弃标签 → (需重判维度, 建议候选新标签)
DEPRECATED_TAG_MAP = {
    "光-柔光":     ("光照",   ["光-黄金时刻", "光-阴天散射", "光-室内漫反射", "光-蓝调时刻"]),
    "兽-巨兽":     ("角色类型", ["角-巨兽"]),
    "兽-魔物":     ("角色类型", ["角-魔物"]),
    "兽-机械兽":   ("角色类型", ["角-机械兽"]),
    "兽-现实动物": ("角色类型", ["角-现实动物"]),
    "兽-变异体":   ("角色类型", ["角-变异体"]),
    "材-磨砂/哑光": ("材质细节", ["材-塑料-磨砂", "材-玻璃-磨砂"]),
    "材-金属":     ("材质细节", ["材-金属-光面", "材-金属-拉丝", "材-金属-生锈",
                                "材-金属-烤漆", "材-金属-做旧", "材-金属-镀铬"]),
    "材-生锈金属": ("材质细节", ["材-金属-生锈"]),
    "材-拉丝金属": ("材质细节", ["材-金属-拉丝"]),
    "材-烤漆":     ("材质细节", ["材-金属-烤漆"]),
    "材-布料":     ("材质细节", ["材-布料-普通", "材-布料-机能", "材-布料-皮革",
                                "材-布料-毛料", "材-布料-丝绸"]),
    "材-皮革":     ("材质细节", ["材-布料-皮革"]),
    "材-机能面料": ("材质细节", ["材-布料-机能"]),
    "材-塑料":     ("材质细节", ["材-塑料-光面", "材-塑料-磨砂"]),
    "材-玻璃":     ("材质细节", ["材-玻璃-清透", "材-玻璃-磨砂", "材-玻璃-彩色"]),
    "材-有机体":   ("材质细节", ["（无直接替换，请根据具体内容判断）"]),
}


def main():
    prog    = json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
    pending = json.loads(PENDING_FILE.read_text(encoding="utf-8")) if PENDING_FILE.exists() else []
    pending_map = {e["item_id"]: e for e in pending}

    records = prog.get("records", [])

    review_rows = []
    reason_counter: dict = defaultdict(list)  # deprecated_tag → [item_ids]

    for r in records:
        item_id    = r["item_id"]
        tags_added = r.get("tags_added", [])

        deprecated_found = [(t, DEPRECATED_TAG_MAP[t]) for t in tags_added if t in DEPRECATED_TAG_MAP]
        if not deprecated_found:
            continue

        existing     = pending_map.get(item_id, {}).get("existing_tags", [])
        all_tags_set = list(dict.fromkeys(existing + tags_added))

        dims        = list(dict.fromkeys(dim for _, (dim, _) in deprecated_found))
        suggestions = list(dict.fromkeys(
            s for _, (_, sugg) in deprecated_found for s in sugg
        ))
        deprecated_names = [t for t, _ in deprecated_found]

        review_rows.append({
            "item_id":    item_id,
            "all_tags":   all_tags_set,
            "deprecated": deprecated_names,
            "dims":       " / ".join(dims),
            "candidates": ", ".join(suggestions),
        })

        for t in deprecated_names:
            reason_counter[t].append(item_id)

    lines = [
        "# review_queue.md — 需回溯重判的 item 清单\n\n",
        f"生成时间：2026-04-23　　涉及条目：{len(review_rows)} 条\n\n",
        "---\n\n",
        "## 统计摘要（按废弃标签分类）\n\n",
        "| 废弃标签 | 涉及条数 |\n",
        "|---|---|\n",
    ]
    for tag, items in sorted(reason_counter.items(), key=lambda x: -len(x[1])):
        lines.append(f"| `{tag}` | {len(items)} |\n")

    lines += [
        "\n---\n\n",
        "## 明细清单\n\n",
        "格式：`item_id | 当前全部标签 | 需重判维度 | 建议新标签候选`\n\n",
        "> 说明：「当前全部标签」含 prepare 时已有的旧标签 + 本轮新增，仅供参考；",
        "实际 Eagle 标签以 Eagle 库为准。不要通过本脚本修改任何数据。\n\n",
        "---\n\n",
    ]
    for row in review_rows:
        item_id   = row["item_id"]
        tags_str  = ", ".join(row["all_tags"]) if row["all_tags"] else "（无）"
        dep_str   = " + ".join(f"`{t}`" for t in row["deprecated"])
        lines.append(
            f"### {item_id}\n\n"
            f"- **废弃标签**: {dep_str}\n"
            f"- **当前全部标签**: {tags_str}\n"
            f"- **需重判维度**: {row['dims']}\n"
            f"- **建议新标签候选**: {row['candidates']}\n\n"
        )

    OUTPUT_FILE.write_text("".join(lines), encoding="utf-8")
    print(f"✅ review_queue.md 已生成，共 {len(review_rows)} 条")
    print("\n按废弃标签统计：")
    for tag, items in sorted(reason_counter.items(), key=lambda x: -len(x[1])):
        print(f"  {tag}: {len(items)} 条")


if __name__ == "__main__":
    main()
