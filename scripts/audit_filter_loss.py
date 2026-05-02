"""审计：stage-1 词表过滤未生效造成的损失。只读。"""
import json
from pathlib import Path
from collections import defaultdict, Counter

BASE = Path(__file__).parent.parent
BATCHES_DIRS = [BASE / "data" / "batches", BASE / "archive" / "batches"]
TAGS_FILE = BASE / "config" / "tags.json"
REPORT = BASE / "reports" / "audit_filter_loss.md"

INCOMPATIBLE_PREFIXES = {
    "类-UI":     ["镜", "光", "氛", "场", "构", "件", "载", "域"],
    "类-排版":   ["镜", "光", "氛", "场", "件", "载", "域"],
    "类-教程":   ["氛"],
    "类-拆解图": ["氛", "光"],
    "类-像素画": ["材"],
}

def load_tags_by_prefix():
    data = json.loads(TAGS_FILE.read_text(encoding="utf-8"))
    out = {}
    for pfx, items in data.get("tags", {}).items():
        out[pfx] = [t["name"] if isinstance(t, dict) else t for t in items]
    return out, sum(len(v) for v in out.values())

def iter_batch_results():
    seen = set()
    for d in BATCHES_DIRS:
        if not d.exists(): continue
        for f in sorted(d.glob("batch_results_*.json")):
            if f.name in seen: continue
            seen.add(f.name)
            data = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(data, dict): data = list(data.values())
            yield f.name, data

def main():
    tags_by_pfx, total_vocab = load_tags_by_prefix()
    total_items = total_success = total_failed = 0
    total_prompt = total_completion = total_cached = 0
    by_primary = defaultdict(lambda: {"count": 0, "tags_total": 0, "tags_blocked": 0, "blocked_prefixes": Counter()})
    no_primary_count = 0
    blocked_prefix_global = Counter()
    tag_count_dist = Counter()

    for fname, items in iter_batch_results():
        for r in items:
            total_items += 1
            status = r.get("status")
            if status == "failed":
                total_failed += 1; continue
            if status != "success": continue
            total_success += 1
            u = r.get("usage", {})
            total_prompt     += u.get("prompt_tokens", 0)
            total_completion += u.get("completion_tokens", 0)
            total_cached     += u.get("cached_tokens", 0)
            tags = r.get("tags_to_add", [])
            tag_count_dist[len(tags)] += 1
            primaries = [t for t in tags if t.startswith("类-")]
            primary = primaries[0] if primaries else None
            if not primary:
                no_primary_count += 1; continue
            blocked_pfxs = INCOMPATIBLE_PREFIXES.get(primary, [])
            blocked = [t for t in tags if any(t.startswith(p + "-") for p in blocked_pfxs)]
            g = by_primary[primary]
            g["count"] += 1
            g["tags_total"] += len(tags)
            g["tags_blocked"] += len(blocked)
            for t in blocked:
                pfx = t.split("-")[0]
                g["blocked_prefixes"][pfx] += 1
                blocked_prefix_global[pfx] += 1

    cached_rate = total_cached / total_prompt if total_prompt else 0
    affected = {p: g for p, g in by_primary.items() if p in INCOMPATIBLE_PREFIXES}
    aff_count = sum(g["count"] for g in affected.values())
    aff_blocked = sum(g["tags_blocked"] for g in affected.values())
    aff_total_tags = sum(g["tags_total"] for g in affected.values())
    global_blocked = sum(g["tags_blocked"] for g in by_primary.values())
    global_total_tags = sum(g["tags_total"] for g in by_primary.values())

    L = []
    L.append("# 词表过滤损失审计\n")
    L.append(f"**词表**: {total_vocab} 标签 / {len(tags_by_pfx)} 前缀")
    L.append(f"**样本**: {total_items} 项 | 成功 {total_success} | 失败 {total_failed}\n")
    L.append("## token 统计\n")
    L.append("| 指标 | 值 |")
    L.append("|---|---|")
    L.append(f"| prompt_tokens | {total_prompt:,} |")
    L.append(f"| completion_tokens | {total_completion:,} |")
    L.append(f"| cached_tokens | {total_cached:,} |")
    L.append(f"| cached 命中率 | {cached_rate*100:.1f}% |")
    L.append(f"| 实际计费 prompt | {total_prompt - total_cached:,} |\n")
    L.append("## 按主类的排异损失\n")
    L.append("| 主类 | 样本 | 平均标签 | 平均被排异 | 排异率 | Top 被排异前缀 |")
    L.append("|---|---|---|---|---|---|")
    for p in sorted(by_primary.keys()):
        g = by_primary[p]
        a_total = g["tags_total"]/g["count"] if g["count"] else 0
        a_blk = g["tags_blocked"]/g["count"] if g["count"] else 0
        rate = g["tags_blocked"]/g["tags_total"] if g["tags_total"] else 0
        top = ", ".join(f"{x}-({c})" for x, c in g["blocked_prefixes"].most_common(3)) or "-"
        marker = " ⚠" if p in INCOMPATIBLE_PREFIXES else ""
        L.append(f"| {p}{marker} | {g['count']} | {a_total:.2f} | {a_blk:.2f} | {rate*100:.1f}% | {top} |")
    L.append(f"\n无主类图: {no_primary_count} 张\n")
    L.append("## 全局被排异前缀 Top\n")
    for pfx, c in blocked_prefix_global.most_common(15):
        L.append(f"- `{pfx}-` : {c} 次")
    L.append("\n## 受排异规则影响的子集\n")
    L.append(f"- 命中排异主类样本: {aff_count} / {total_success} ({aff_count/max(total_success,1)*100:.1f}%)")
    L.append(f"- 这部分平均每张被丢: {aff_blocked/max(aff_count,1):.2f} 个标签")
    L.append(f"- 全局排异率: {global_blocked}/{global_total_tags} = {global_blocked/max(global_total_tags,1)*100:.1f}%\n")
    L.append("## 标签数分布\n")
    for k in sorted(tag_count_dist):
        L.append(f"- {k} 个标签: {tag_count_dist[k]} 张")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(L), encoding="utf-8")

    print(f"✅ {REPORT.relative_to(BASE)}")
    print(f"   样本: {total_success} 成功 / {total_failed} 失败")
    print(f"   tokens: prompt={total_prompt:,} completion={total_completion:,} cached={total_cached:,} ({cached_rate*100:.1f}%)")
    print(f"   全局排异率: {global_blocked}/{global_total_tags} = {global_blocked/max(global_total_tags,1)*100:.1f}%")
    print(f"   受影响子集: {aff_count}/{total_success} 张 ({aff_count/max(total_success,1)*100:.1f}%)，平均丢 {aff_blocked/max(aff_count,1):.2f} 标签/张")

if __name__ == "__main__":
    main()
