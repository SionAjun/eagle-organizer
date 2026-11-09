"""v2.5 新前缀定向测试 — 15 张
不做任何写入(Eagle / progress / batches),仅输出标签结果。
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tag_real import (
    iter_items, build_messages, call_mimo, _extract_tags,
    load_json, PROGRESS_FILE, resolve_path,
)

PICK_COUNT = 15

def main():
    prog = load_json(PROGRESS_FILE, {})
    processed = set(prog.get("processed_ids", []))

    # 收集未处理候选
    candidates = []
    for item in iter_items():
        if item["id"] in processed:
            continue
        name = item.get("name", "").lower()
        candidates.append(item)
        if len(candidates) >= 300:  # 取前 300 个候选
            break

    print(f"候选池: {len(candidates)} 张未处理")

    # 定向挑选: 优先选文件名含人物/文化/动态关键词的
    char_kw = ["character", "portrait", "girl", "woman", "man", "warrior", "knight",
                "person", "people", "face", "hero", "soldier", "assassin", "mage",
                "人物", "角色", "战士", "少女", "骑士", "刺客", "法师", "士兵"]
    cult_kw = ["victorian", "cyber", "steampunk", "chinese", "japanese", "norse",
               "gothic", "baroque", "medieval", "samurai", "ninja",
               "维多利亚", "赛博", "蒸汽朋克", "中式", "日式", "和风", "中世纪", "哥特"]
    dyn_kw = ["battle", "fight", "action", "dynamic", "combat", "war", "mecha",
              "战斗", "动作", "机甲", "战争"]

    picked = []
    used_ids = set()

    def pick_by_keyword(kw_list, bucket_name):
        for c in candidates:
            if c["id"] in used_ids:
                continue
            name = c.get("name", "").lower()
            if any(k in name for k in kw_list):
                picked.append((c, bucket_name))
                used_ids.add(c["id"])
                if len(picked) >= PICK_COUNT:
                    return

    # 先按关键词挑
    pick_by_keyword(char_kw, "人物")
    pick_by_keyword(cult_kw, "文化")
    pick_by_keyword(dyn_kw, "动态")

    # 不够 15 张则补齐
    for c in candidates:
        if len(picked) >= PICK_COUNT:
            break
        if c["id"] not in used_ids:
            picked.append((c, "补充"))
            used_ids.add(c["id"])

    picked = picked[:PICK_COUNT]
    print(f"选定 {len(picked)} 张:\n")

    # 跑批
    results = []
    for i, (item, reason) in enumerate(picked, 1):
        item_id = item["id"]
        name = item.get("name", "")
        ext = item.get("ext", "")
        print(f"[{i}/{PICK_COUNT}] {item_id} ({name}.{ext}) [{reason}]")

        try:
            messages = build_messages(item)
            resp = call_mimo(messages)
            if resp is None:
                print(f"  ❌ LLM 调用失败")
                results.append({"item_id": item_id, "name": f"{name}.{ext}", "reason": reason, "tags": [], "error": "LLM failed"})
                continue

            tags = resp["tags"]
            usage = resp["usage"]
            print(f"  标签({len(tags)}): {tags}")
            print(f"  tokens: prompt={usage['prompt_tokens']} cached={usage['cached_tokens']}")
            results.append({
                "item_id": item_id,
                "name": f"{name}.{ext}",
                "reason": reason,
                "tags": tags,
                "usage": usage,
            })
        except Exception as e:
            print(f"  ❌ 异常: {e}")
            results.append({"item_id": item_id, "name": f"{name}.{ext}", "reason": reason, "tags": [], "error": str(e)})

        time.sleep(0.5)

    # 统计
    print("\n" + "=" * 60)
    print("统计")
    print("=" * 60)

    new_prefixes = {"代-": [], "姿-": [], "服-": [], "职-": []}
    for r in results:
        for t in r.get("tags", []):
            for pfx in new_prefixes:
                if t.startswith(pfx):
                    new_prefixes[pfx].append(t)

    print(f"\n{'前缀':<6} {'出现次数':>8}  具体标签")
    print("-" * 50)
    for pfx, tags in new_prefixes.items():
        unique = sorted(set(tags))
        count = len(tags)
        tag_str = ", ".join(unique) if unique else "(无)"
        status = "✅" if count > 0 else "❌"
        print(f"{status} {pfx:<4} {count:>6}    {tag_str}")

    # 输出 JSON
    out_path = "data/pilot_v25_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n结果已写入 {out_path}")


if __name__ == "__main__":
    main()
