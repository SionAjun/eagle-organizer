import json, os, statistics, random
from collections import Counter

# Collect all batch files
batch_files = []
for d in ['archive/batches', '.']:
    if os.path.isdir(d):
        for f in sorted(os.listdir(d)):
            if f.startswith('batch_results_') and f.endswith('.json'):
                batch_files.append(os.path.join(d, f))
batch_files = sorted(set(batch_files))
print('Found batch files:', len(batch_files))

# Read all entries
all_entries = []
for bf in batch_files:
    with open(bf, 'r', encoding='utf-8') as f:
        data = json.load(f)
        all_entries.extend(data)
print('Total entries:', len(all_entries))

# Target prefixes: 类-排版, 类-UI
target_tags = ['类-排版', '类-UI']

# Per-image: count of tags matching these prefixes
img_tag_counts = {}
for entry in all_entries:
    item_id = entry['item_id']
    matching = [t for t in entry.get('tags_to_add', []) if t in target_tags]
    img_tag_counts[item_id] = matching

counts = [len(v) for v in img_tag_counts.values()]
counts_nonzero = [c for c in counts if c > 0]

# (a) stats
if counts_nonzero:
    sorted_c = sorted(counts_nonzero)
    n = len(sorted_c)
    mean = statistics.mean(sorted_c)
    median = statistics.median(sorted_c)
    p10 = sorted_c[int(n * 0.1)]
    p90 = sorted_c[int(n * 0.9)]
    mx = max(sorted_c)
else:
    n = mean = median = p10 = p90 = mx = 0

total = len(counts)

# (b) tag frequencies
tag_freq = Counter()
for tags in img_tag_counts.values():
    for t in tags:
        tag_freq[t] += 1

# (c) images with <= 2 matching tags
low_imgs = [(iid, tags) for iid, tags in img_tag_counts.items() if 0 < len(tags) <= 2]
random.seed(42)
sample = random.sample(low_imgs, min(20, len(low_imgs)))

# (d) zero match
zero_count = sum(1 for c in counts if c == 0)

# Read taxonomy
with open('config/tags.json', 'r', encoding='utf-8') as f:
    taxonomy = json.load(f)

# Registered 类-排版 / 类-UI tags
registered_tuipai = set()
for t in taxonomy['tags'].get('类', []):
    if t.startswith('类-排版') or t.startswith('类-UI'):
        registered_tuipai.add(t)

used = set(tag_freq.keys())
unused_tuipai = registered_tuipai - used

# 版- prefix stats
registered_ban = set(taxonomy['tags'].get('版', []))
used_ban = Counter()
for entry in all_entries:
    for t in entry.get('tags_to_add', []):
        if t.startswith('版-'):
            used_ban[t] += 1
unused_ban = registered_ban - set(used_ban.keys())

# Percentages
pct_zero = zero_count / total * 100 if total else 0
pct_cover = (total - zero_count) / total * 100 if total else 0

# Generate report
os.makedirs('reports', exist_ok=True)

with open('reports/typography_ui_density_audit.md', 'w', encoding='utf-8') as f:
    f.write('# 版式/UI 标签颗粒度审计\n\n')
    f.write(f'> 扫描范围: {len(batch_files)} 个 batch 文件, {total} 张图\n\n')

    # (a)
    f.write('## (a) 每张图标签数统计（类-排版 + 类-UI）\n\n')
    f.write('| 指标 | 值 |\n')
    f.write('|------|---|\n')
    f.write(f'| 图片总数 | {total} |\n')
    f.write(f'| 含 ≥1 匹配标签的图片数 | {n} |\n')
    f.write(f'| mean | {mean:.2f} |\n')
    f.write(f'| median | {median} |\n')
    f.write(f'| P10 | {p10} |\n')
    f.write(f'| P90 | {p90} |\n')
    f.write(f'| max | {mx} |\n\n')

    # (b)
    f.write('## (b) 所有标签频次（降序）\n\n')
    f.write('| 标签 | 频次 |\n')
    f.write('|------|------|\n')
    for tag, freq in tag_freq.most_common():
        f.write(f'| {tag} | {freq} |\n')

    # 版- prefix
    f.write('\n### 版- 前缀标签频次\n\n')
    f.write('| 标签 | 频次 |\n')
    f.write('|------|------|\n')
    for tag, freq in used_ban.most_common():
        f.write(f'| {tag} | {freq} |\n')
    for tag in sorted(unused_ban):
        f.write(f'| {tag} | 0 |\n')

    # (c)
    f.write('\n## (c) 标签数 ≤ 2 的图片（随机抽 20 张）\n\n')
    f.write('| item_id | 已打标签 |\n')
    f.write('|---------|----------|\n')
    for iid, tags in sample:
        tag_str = ', '.join(tags) if tags else '(无)'
        f.write(f'| {iid} | {tag_str} |\n')

    # (d)
    f.write('\n## (d) 未命中统计\n\n')
    f.write('| 指标 | 值 |\n')
    f.write('|------|---|\n')
    f.write(f'| 未命中图片数 | {zero_count} |\n')
    f.write(f'| 总图片数 | {total} |\n')
    f.write(f'| 未命中占比 | {pct_zero:.1f}% |\n')
    f.write(f'| 覆盖率 | {pct_cover:.1f}% |\n\n')

    # (e) taxonomy diff
    f.write('## (e) 词表差集（注册但从未使用）\n\n')
    f.write('### 类-排版 / 类-UI\n\n')
    if unused_tuipai:
        f.write('| 标签 |\n')
        f.write('|------|\n')
        for t in sorted(unused_tuipai):
            f.write(f'| {t} |\n')
    else:
        f.write('无 — 所有注册标签均已被使用。\n')

    f.write('\n### 版- 前缀\n\n')
    if unused_ban:
        f.write('| 标签 |\n')
        f.write('|------|\n')
        for t in sorted(unused_ban):
            f.write(f'| {t} |\n')
    else:
        f.write('无 — 所有注册标签均已被使用。\n')

# Console summary
print(f'\n=== RESULTS ===')
print(f'Report: reports/typography_ui_density_audit.md')
print(f'(a) mean={mean:.2f} median={median} P10={p10} P90={p90} max={mx}')
print(f'(d) zero={zero_count}/{total} coverage={pct_cover:.1f}%')
