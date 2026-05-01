import json, random, urllib.request
from pathlib import Path

random.seed(42)
batch_ids = [f"{i:03d}" for i in range(27, 52)]
all_items = []
for bid in batch_ids:
    p = Path(f"data/batches/batch_results_{bid}.json")
    if not p.exists():
        continue
    data = json.load(open(p, encoding="utf-8"))
    if isinstance(data, list):
        all_items.extend(data)
    elif isinstance(data, dict):
        all_items.extend(data.values())

EAGLE_API = "http://localhost:41595/api"
_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def eagle_item_info(item_id: str) -> dict:
    try:
        with _opener.open(f"{EAGLE_API}/item/info?id={item_id}", timeout=10) as r:
            return json.loads(r.read()).get("data", {})
    except Exception:
        return {}


def eagle_deeplink(item_id: str) -> str:
    return f"eagle://item/{item_id}"


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


picked = []
for filt in [is_vehicle, is_layout, is_school, is_char]:
    cands = [it for it in all_items if filt(it.get("tags_to_add", []))]
    if cands:
        picked.append(random.choice(cands))

remaining = [it for it in all_items if it not in picked]
picked.extend(random.sample(remaining, max(0, 10 - len(picked))))

with open("reports/v24_human_baseline.md", "w", encoding="utf-8") as f:
    f.write("# v2.4 时代人工基线（10 张抽样）\n\n")
    f.write("人工判定列: 好 / 坏 / 部分，在「人工」列直接填\n\n")
    f.write("| # | 文件名 | Eagle 链接 | 自动标签 | 人工 | 备注 |\n")
    f.write("|---|---|---|---|---|---|\n")
    for i, it in enumerate(picked, 1):
        item_id = it.get("item_id", "?")
        info = eagle_item_info(item_id)
        name = info.get("name", item_id)
        ext = info.get("ext", "")
        fname = f"{name}.{ext}" if ext else name
        link = eagle_deeplink(item_id)
        tags = " / ".join(it.get("tags_to_add", []))
        f.write(f"| {i} | {fname} | [打开]({link}) | {tags} |  |  |\n")

print("Done -> reports/v24_human_baseline.md")
