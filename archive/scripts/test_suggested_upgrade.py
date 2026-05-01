"""
test_suggested_upgrade.py — Mini test for suggested_tags.json v1.1 upgrade.
Uses temp files only. Does NOT touch real data files or Eagle API.
Run: python test_suggested_upgrade.py
"""
import json
import tempfile
from pathlib import Path
from datetime import datetime

TODAY   = datetime.now().strftime("%Y-%m-%d")
NOW_STR = datetime.now().strftime("%Y-%m-%d %H:%M")

# ── logic mirrors (inline copy of the new tag_real.py logic) ─────────────────

def save_json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

def load_json(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default

def apply_suggested(sfile: Path, tag: str, item_id: str):
    """Mirrors the new cmd_apply suggested write block."""
    sdata = load_json(sfile, {"version": "1.1", "suggested": {}})
    smap  = sdata.setdefault("suggested", {})
    if tag in smap:
        smap[tag]["count"] += 1
        ex = smap[tag].setdefault("example_items", [])
        if item_id not in ex:
            ex.append(item_id)
            if len(ex) > 5:
                smap[tag]["example_items"] = ex[-5:]
        smap[tag]["last_seen"] = TODAY
    else:
        smap[tag] = {
            "count": 1,
            "example_items": [item_id],
            "first_seen": TODAY,
            "last_seen": TODAY,
        }
    save_json(sfile, sdata)

def checkpoint_pending_review(sfile: Path, review_file: Path) -> list:
    """Mirrors the new run_checkpoint pending_review block."""
    sdata = load_json(sfile, {"version": "1.1", "suggested": {}})
    smap  = sdata.get("suggested", {})
    pending = [k for k, v in smap.items() if v.get("count", 0) >= 3]
    if pending:
        lines = [f"# 待审标签（count≥3）\n\n生成时间：{NOW_STR}\n\n---\n"]
        for tag in pending:
            entry = smap[tag]
            lines.append(f"\n## `{tag}`\n\n")
            lines.append(f"- **count**: {entry['count']}\n")
            lines.append(f"- **example_items**: {entry.get('example_items', [])}\n")
            lines.append(f"- **first_seen**: {entry.get('first_seen', '?')}\n")
            lines.append(f"- **last_seen**: {entry.get('last_seen', '?')}\n")
            lines.append(f"- **决定**: （填 yes 加入词表 / 填 no 忽略）\n")
        review_file.write_text("".join(lines), encoding="utf-8")
    return pending

# ── tests ─────────────────────────────────────────────────────────────────────

def run_tests():
    with tempfile.TemporaryDirectory() as _tmp:
        tmp = Path(_tmp)

        # ── TEST 1: count 累加，同一标签 × 3 张不同 item ─────────────────────
        print("=" * 52)
        print("TEST 1: count 累加（同一标签 × 3 次，3 个不同 item）")
        print("=" * 52)
        sf1 = tmp / "s1.json"
        tag = "物-测试线缆"
        items = ["ITEM001", "ITEM002", "ITEM003"]
        for it in items:
            apply_suggested(sf1, tag, it)
        d = load_json(sf1, {})
        e = d["suggested"][tag]
        assert e["count"] == 3,              f"FAIL: count={e['count']} 应为 3"
        assert e["example_items"] == items,  f"FAIL: example_items={e['example_items']}"
        assert e["first_seen"] == TODAY,     f"FAIL: first_seen={e['first_seen']}"
        assert e["last_seen"]  == TODAY,     f"FAIL: last_seen={e['last_seen']}"
        print(f"  ✅ count={e['count']}, example_items={e['example_items']}")

        # ── TEST 2: example_items 超 5 时保留最近 5 ──────────────────────────
        print()
        print("=" * 52)
        print("TEST 2: example_items 超 5 时只保留最近 5 个")
        print("=" * 52)
        sf2 = tmp / "s2.json"
        tag2 = "物-超量标签"
        items7 = [f"ITEM{i:03d}" for i in range(1, 8)]  # 7 items
        for it in items7:
            apply_suggested(sf2, tag2, it)
        d2 = load_json(sf2, {})
        e2 = d2["suggested"][tag2]
        assert e2["count"] == 7,                      f"FAIL: count={e2['count']} 应为 7"
        assert len(e2["example_items"]) == 5,          f"FAIL: len={len(e2['example_items'])} 应为 5"
        assert e2["example_items"] == items7[-5:],     f"FAIL: 应保留最近 5 个: {e2['example_items']}"
        print(f"  ✅ count={e2['count']}, 保留最近 5 个: {e2['example_items']}")

        # ── TEST 3: 检查点生成 pending_review.md（count≥3） ──────────────────
        print()
        print("=" * 52)
        print("TEST 3: 检查点生成 pending_review.md（count≥3）")
        print("=" * 52)
        rv1 = tmp / "rv1.md"
        pending = checkpoint_pending_review(sf1, rv1)
        assert len(pending) == 1 and pending[0] == tag, f"FAIL: pending={pending}"
        assert rv1.exists(),                            "FAIL: pending_review.md 未生成"
        content = rv1.read_text(encoding="utf-8")
        assert f"## `{tag}`" in content,               "FAIL: 标签标题缺失"
        assert "**count**: 3" in content,               "FAIL: count 行缺失"
        print(f"  ✅ pending_review.md 已生成，{len(pending)} 条 count≥3")
        print(f"  内容预览:\n{content[:400]}")

        # ── TEST 4: count<3 的标签不触发 pending_review.md ───────────────────
        print()
        print("=" * 52)
        print("TEST 4: count<3 不生成 pending_review.md")
        print("=" * 52)
        sf4 = tmp / "s4.json"
        rv4 = tmp / "rv4.md"
        apply_suggested(sf4, "物-低频标签", "ITEM_A")
        apply_suggested(sf4, "物-低频标签", "ITEM_B")  # count=2，未到 3
        pending4 = checkpoint_pending_review(sf4, rv4)
        assert len(pending4) == 0,   f"FAIL: count=2 不应进入 pending_review: {pending4}"
        assert not rv4.exists(),     "FAIL: count<3 时不应生成文件"
        print(f"  ✅ count=2 的标签未进入 pending_review.md")

        # ── TEST 5: 重复 item_id 不重复计入 example_items ────────────────────
        print()
        print("=" * 52)
        print("TEST 5: 相同 item_id 重复打标不重复进 example_items")
        print("=" * 52)
        sf5 = tmp / "s5.json"
        tag5 = "物-去重标签"
        apply_suggested(sf5, tag5, "SAME_ITEM")
        apply_suggested(sf5, tag5, "SAME_ITEM")  # 同一 item 第二次
        apply_suggested(sf5, tag5, "OTHER_ITEM")
        d5 = load_json(sf5, {})
        e5 = d5["suggested"][tag5]
        assert e5["count"] == 3,                          f"FAIL: count={e5['count']} 应为 3"
        assert e5["example_items"] == ["SAME_ITEM", "OTHER_ITEM"], \
            f"FAIL: example_items={e5['example_items']}"
        print(f"  ✅ count={e5['count']}, example_items={e5['example_items']}（无重复）")

    print()
    print("=" * 52)
    print("全部 5 项测试通过 ✅")
    print("=" * 52)

if __name__ == "__main__":
    run_tests()
