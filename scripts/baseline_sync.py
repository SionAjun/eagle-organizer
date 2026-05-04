"""把 md 里的人填判定回写到 jsonl, 并追加到 index.jsonl"""

import json
import re
import sys
from pathlib import Path

BASELINES_DIR = Path("data/baselines")


def derive_overall(wrong_tags: list) -> str:
    """根据错标自动推 overall:
    - wrong_tags 数量为 0 → "好"
    - wrong_tags 数量 1-2, 且不含 "类-*" 前缀 → "部分"
    - wrong_tags 数量 >= 3, 或含任一 "类-*" 前缀 → "坏"
    """
    if len(wrong_tags) == 0:
        return "好"
    if any(t.startswith("类-") for t in wrong_tags):
        return "坏"
    if len(wrong_tags) >= 3:
        return "坏"
    return "部分"


def parse_md(md_path: Path) -> dict:
    """解析 md, 返回 {item_id: judgment} 字典"""
    text = md_path.read_text(encoding="utf-8")
    results = {}

    # 按 ### #N 切块
    blocks = re.split(r"^### #\d+", text, flags=re.MULTILINE)

    # 第一块是头部, 跳过; 后续每块对应一张图
    header_pattern = re.compile(r"^\[打开\]\(eagle://item/(\w+)\)", re.MULTILINE)

    for block in blocks[1:]:
        m_id = header_pattern.search(block)
        if not m_id:
            continue
        item_id = m_id.group(1)

        # 解析 错标
        wrong_match = re.search(r"^\-\s*\*\*错标\*\*:[ \t]*(.*?)$", block, re.MULTILINE)
        wrong_tags = []
        if wrong_match:
            val = wrong_match.group(1).strip()
            if val and val != "无":
                wrong_tags = [t.strip() for t in re.split(r"[/,]", val) if t.strip()]

        # 解析 漏标
        missing_match = re.search(r"^\-\s*\*\*漏标\*\*:[ \t]*(.*?)$", block, re.MULTILINE)
        missing_tags = []
        if missing_match:
            val = missing_match.group(1).strip()
            if val and val != "无":
                missing_tags = [t.strip() for t in re.split(r"[/,]", val) if t.strip()]

        # 解析 备注
        note_match = re.search(r"^\-\s*\*\*备注\*\*:[ \t]*(.*?)$", block, re.MULTILINE)
        note = ""
        if note_match:
            note = note_match.group(1).strip()

        # 自动推 overall
        overall = derive_overall(wrong_tags)

        results[item_id] = {
            "overall": overall,
            "wrong_tags": wrong_tags,
            "missing_tags": missing_tags,
            "note": note
        }

    return results


def merge_jsonl(jsonl_path: Path, judgments: dict) -> tuple:
    """把 judgment 合并到 jsonl, 返回 (records, filled_count)"""
    records = []
    filled = 0
    with open(jsonl_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            item_id = rec.get("item_id", "")
            if item_id in judgments:
                rec["judgment"] = judgments[item_id]
                # 错标/漏标/备注 任一非空即视为已填
                j = judgments[item_id]
                if j["wrong_tags"] or j["missing_tags"] or j["note"]:
                    filled += 1
            records.append(rec)
    return records, filled


def write_jsonl(jsonl_path: Path, records: list):
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def append_to_index(records: list):
    """追加到 index.jsonl, 按 sample_id 去重(新版替换旧版)"""
    index_path = BASELINES_DIR / "index.jsonl"
    existing = {}
    if index_path.exists():
        with open(index_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    sid = rec.get("sample_id", "")
                    if sid:
                        existing[sid] = rec
                except json.JSONDecodeError:
                    pass

    for rec in records:
        sid = rec.get("sample_id", "")
        if sid:
            existing[sid] = rec

    with open(index_path, "w", encoding="utf-8") as f:
        for rec in existing.values():
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    return len(existing)


def main():
    if len(sys.argv) < 2:
        print("用法: python baseline_sync.py NNN")
        print("  把 baseline_NNN.md 的判定回写到 baseline_NNN.jsonl, 并追加到 index.jsonl")
        sys.exit(1)

    nnn = sys.argv[1].zfill(3)
    md_path = BASELINES_DIR / f"baseline_{nnn}.md"
    jsonl_path = BASELINES_DIR / f"baseline_{nnn}.jsonl"

    if not md_path.exists():
        print(f"错误: {md_path} 不存在")
        sys.exit(1)
    if not jsonl_path.exists():
        print(f"错误: {jsonl_path} 不存在")
        sys.exit(1)

    # 解析 md
    judgments = parse_md(md_path)
    print(f"从 {md_path.name} 解析到 {len(judgments)} 条判定")

    # 合并到 jsonl
    records, filled = merge_jsonl(jsonl_path, judgments)
    write_jsonl(jsonl_path, records)
    print(f"已回写 {jsonl_path.name}")

    # 追加到 index.jsonl
    total_in_index = append_to_index(records)

    # 报告
    total = len(records)
    empty = total - filled

    # overall 分布
    overall_dist = {"好": 0, "部分": 0, "坏": 0}
    for rec in records:
        ov = rec.get("judgment", {}).get("overall")
        if ov in overall_dist:
            overall_dist[ov] += 1

    print(f"\n--- 报告 ---")
    print(f"本批 {total} 条样本")
    print(f"已填 {filled} 条 (错标/漏标/备注 任一非空)")
    print(f"空 {empty} 条")
    print(f"overall 分布: 好 {overall_dist['好']} 条 / 部分 {overall_dist['部分']} 条 / 坏 {overall_dist['坏']} 条")
    print(f"index.jsonl 累计 {total_in_index} 条")


if __name__ == "__main__":
    main()
