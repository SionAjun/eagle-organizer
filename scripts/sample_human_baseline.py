"""生成人工基线抽样 — 同时输出 .md (供人填) 和 .jsonl (结构化数据)"""

import argparse
import json
import random
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASELINES_DIR = Path("data/baselines")
EAGLE_API = "http://localhost:41595/api"
_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

FOCUS_ROTATION = ["派-", "氛-", "件-", "材-", "镜-"]


def next_batch_id() -> int:
    """扫描 data/baselines/ 取最大 baseline_NNN 序号 + 1"""
    BASELINES_DIR.mkdir(parents=True, exist_ok=True)
    max_n = 0
    for p in BASELINES_DIR.glob("baseline_*.md"):
        try:
            n = int(p.stem.split("_")[1])
            max_n = max(max_n, n)
        except (IndexError, ValueError):
            pass
    return max_n + 1


def detect_focus() -> str:
    """读 index.jsonl 看上次用的 focus_prefix, 轮到下一个"""
    index_path = BASELINES_DIR / "index.jsonl"
    if not index_path.exists():
        return FOCUS_ROTATION[0]
    last_focus = ""
    with open(index_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                last_focus = obj.get("focus_prefix", "")
            except json.JSONDecodeError:
                pass
    if last_focus in FOCUS_ROTATION:
        idx = FOCUS_ROTATION.index(last_focus)
        return FOCUS_ROTATION[(idx + 1) % len(FOCUS_ROTATION)]
    return FOCUS_ROTATION[0]


def eagle_item_info(item_id: str) -> dict:
    try:
        with _opener.open(f"{EAGLE_API}/item/info?id={item_id}", timeout=10) as r:
            return json.loads(r.read()).get("data", {})
    except Exception:
        return {}


def has(tags, prefix):
    return any(t.startswith(prefix) for t in tags)


def is_layout(tags):
    return has(tags, "类-排版") or has(tags, "类-UI")


def is_vehicle(tags):
    return has(tags, "载-")


def is_school(tags):
    return has(tags, "派-")


def is_char(tags):
    return has(tags, "类-角色") and has(tags, "风-写实")


def load_all_items() -> list:
    """加载 batch 027-054 的所有条目"""
    all_items = []
    for i in range(27, 55):
        p = Path(f"data/batches/batch_results_{i:03d}.json")
        if not p.exists():
            continue
        data = json.load(open(p, encoding="utf-8"))
        if isinstance(data, list):
            all_items.extend(data)
        elif isinstance(data, dict):
            all_items.extend(data.values())
    return all_items


def sample_items(all_items: list, seed: int = 42) -> list:
    """分层抽样: 先从 4 个类别各取 1 张, 再随机补到 10 张. 返回 (items, reasons)"""
    random.seed(seed)
    picked = []
    reasons = []
    category_names = ["载具分层", "排版分层", "风格派分层", "角色分层"]
    for filt, reason in zip([is_vehicle, is_layout, is_school, is_char], category_names):
        cands = [it for it in all_items if filt(it.get("tags_to_add", []))]
        if cands:
            picked.append(random.choice(cands))
            reasons.append(reason)
    remaining = [it for it in all_items if it not in picked]
    n_random = max(0, 10 - len(picked))
    picked.extend(random.sample(remaining, n_random))
    reasons.extend(["随机补充"] * n_random)
    return picked, reasons


def render_md(batch_id: int, items: list, focus: str) -> str:
    """渲染新格式 md"""
    lines = []
    lines.append(f"# 人工基线 batch {batch_id:03d}")
    lines.append("")
    lines.append(f"**focus_prefix**: {focus}")
    lines.append(f"**抽样时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"**样本数**: {len(items)}")
    lines.append("")
    lines.append("---")
    lines.append("")
    for i, it in enumerate(items, 1):
        item_id = it.get("item_id", "?")
        info = eagle_item_info(item_id)
        name = info.get("name", item_id)
        ext = info.get("ext", "")
        tags = it.get("tags_to_add", [])
        tags_str = " / ".join(tags)
        lines.append(f"### #{i} {name}.{ext}")
        lines.append(f"[打开](eagle://item/{item_id})")
        lines.append("")
        lines.append(f"**自动标签**: {tags_str}")
        lines.append("")
        lines.append("- **错标**: ")
        lines.append("- **漏标**: ")
        lines.append("- **备注**: ")
        lines.append("")
    return "\n".join(lines)


def build_jsonl(batch_id: int, items: list, reasons: list, focus: str, progress_count: int) -> list:
    """构建 jsonl 记录列表"""
    now = datetime.now(timezone.utc).isoformat()
    records = []
    for i, (it, reason) in enumerate(zip(items, reasons), 1):
        item_id = it.get("item_id", "?")
        info = eagle_item_info(item_id)
        name = info.get("name", item_id)
        ext = info.get("ext", "")
        tags = it.get("tags_to_add", [])
        records.append({
            "sample_id": f"{batch_id:03d}-{i}",
            "batch_id": batch_id,
            "item_id": item_id,
            "name": name,
            "ext": ext,
            "auto_tags": tags,
            "sample_reason": reason,
            "focus_prefix": focus,
            "sampled_at": now,
            "from_progress_count": progress_count,
            "judgment": {
                "overall": None,
                "wrong_tags": [],
                "missing_tags": [],
                "note": ""
            }
        })
    return records


def main():
    parser = argparse.ArgumentParser(description="生成人工基线抽样 (md + jsonl)")
    parser.add_argument("--focus", type=str, default="", help="重点关注前缀, 如 派- (默认自动轮换)")
    parser.add_argument("--seed", type=int, default=42, help="随机种子 (默认 42)")
    args = parser.parse_args()

    BASELINES_DIR.mkdir(parents=True, exist_ok=True)

    batch_id = next_batch_id()
    focus = args.focus if args.focus else detect_focus()

    # 加载 progress.json 获取 total_processed
    prog_path = Path("data/progress.json")
    progress_count = 0
    if prog_path.exists():
        prog = json.load(open(prog_path, encoding="utf-8"))
        progress_count = prog.get("total_processed", 0)

    all_items = load_all_items()
    picked, reasons = sample_items(all_items, seed=args.seed)

    # 写 md
    md_content = render_md(batch_id, picked, focus)
    md_path = BASELINES_DIR / f"baseline_{batch_id:03d}.md"
    md_path.write_text(md_content, encoding="utf-8")

    # 写 jsonl
    records = build_jsonl(batch_id, picked, reasons, focus, progress_count)
    jsonl_path = BASELINES_DIR / f"baseline_{batch_id:03d}.jsonl"
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"Done -> {md_path}")
    print(f"       {jsonl_path}")
    print(f"batch_id={batch_id}, focus={focus}, samples={len(records)}")


if __name__ == "__main__":
    main()
