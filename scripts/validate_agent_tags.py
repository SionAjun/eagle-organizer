"""校验 agent 产出的标签结果文件：词表合法性 + 排异规则冲突。

在 `python tag_real.py --apply-agent <file>` 之前跑，把词表拼错、前缀用错
（例如把 `角-全身` 写成 `镜-全身`）挡在写回 Eagle 之前。

用法：
    python scripts/validate_agent_tags.py <结果文件> [<结果文件> ...]

退出码：0 = 全部合法；1 = 有问题（详情打印到 stdout）。
"""
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import rules_engine  # noqa: E402


def load_valid_tags() -> tuple:
    data = json.loads((BASE_DIR / "config" / "tags.json").read_text(encoding="utf-8"))
    valid, by_name = set(), {}
    for pfx, tags in data["tags"].items():
        for x in tags:
            name = x if isinstance(x, str) else x["name"]
            valid.add(name)
            by_name.setdefault(name.split("-", 1)[-1], []).append(name)
    return valid, by_name


def check(path: Path, valid: set, by_suffix: dict) -> int:
    entries = json.loads(path.read_text(encoding="utf-8"))
    problems = 0
    seen = set()
    for e in entries:
        iid = e.get("item_id", "<无 item_id>")
        if iid in seen:
            print(f"  [重复] {iid} 在同一文件里出现多次")
            problems += 1
        seen.add(iid)

        tags = e.get("tags_to_add", [])
        for t in tags:
            if t in valid:
                continue
            problems += 1
            suffix = t.split("-", 1)[-1]
            hint = by_suffix.get(suffix)
            if hint:
                print(f"  [词表外] {iid}: {t} → 前缀用错？词表里是 {hint}")
            else:
                print(f"  [词表外] {iid}: {t}")

        blocked = rules_engine.get_blocked_prefixes_from_tags(tags)
        if blocked:
            bad = [t for t in tags if any(t.startswith(p + "-") for p in blocked)]
            if bad:
                print(f"  [排异] {iid}: 主类屏蔽前缀 {blocked}，冲突标签 {bad}（写回时会被丢弃）")
                problems += 1

        if not tags:
            print(f"  [空标签] {iid}: tags_to_add 为空，会记为 agent_unclassified")

    print(f"{path.name}: {len(entries)} 条，问题 {problems} 处")
    return problems


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    valid, by_suffix = load_valid_tags()
    total = sum(check(Path(p), valid, by_suffix) for p in sys.argv[1:])
    print("✅ 全部合法" if total == 0 else f"❌ 合计 {total} 处问题")
    return 0 if total == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
