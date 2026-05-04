<!-- AUTO-GENERATED FROM /config/. DO NOT EDIT.
     Last sync: 2026-05-04 15:00:00 from tags.json v2.4 -->

# Eagle 打标项目 — 新对话开场交接文档


> 新会话开始时只需粘贴本文件，无需其他文档。

---

## 当前进度

- 已处理：**970 / 20378** 张（4.76%）
- 批次号：55
- 最后 item_id：`MON605ZTVACYZ`
- 人工基线：baseline_001（派-）+ baseline_002（构-），index.jsonl 累计 20 条
- 洞察总账：`data/baselines/insights.md`（6 大类，主线 1 评审核心输入）

---

## 当前词表版本与近期变更

tags.json v2.4，317 标签 / 19 前缀

最近 5 条变更：
- 2026-04-23  tags.json v2.0：兽前缀废除，5 个迁入角
- 以 tag_real.py 顶部 INCOMPATIBLE_PREFIXES 为真相，重写 config/rules.json 的 incompatible_prefixes 字段
- 此前两处不一致：rules.json 是早期设想（4 前缀 / 3 类目），tag_real.py 是实际生效版本（8 前缀 / 5 类目，已经过 580 张图实证）
- 砍掉 rules.json 里孤立的 "类-实景参考" 规则（从未生效过，且与用户实际打标习惯冲突——实景参考图需要保留光/镜/氛/场标签）
- 本次仅同步配置文件，不改动运行时逻辑；接通由 a1-2 完成

---

## 用户偏好（config/preferences.json 全量）

- 角色：概念设计师 / 游戏美术
- 意图：翻图为偷美学，不是研究 UI 功能
- 格- 权重：最高权重，主检索入口；游戏美学锚点
- 版- 权重：次高权重；类-UI / 类-排版 必判
- 风- 权重：纯绘画技法，不再含作品名
- 禁止维度：面-HUD / 面-菜单 等 UI 功能拆解维度（绝不要建）
- 食物素材：仅 1 个粗粒度标签，按现状处理

---

## 已知坑（手工维护，超 8 条时归档到 docs/pitfalls.md）

1. 系统代理劫持 localhost → ProxyHandler({}) 绕过
2. limit 小时分页截断 → 统一 limit=1000
3. Eagle API 无总数字段 → limit=25000 探底
4. orderBy=-CREATEDATE 排序反了 → 去掉 orderBy
5. btime=0 老素材 → 改用 modificationTime
6. /api/v2/ 端点不存在 → 用 /api/ 前缀

---

## 待处理清单（不主动 surface）

- suggested_tags.json count≥3 待审：3 个
- exceptions.json 累计：1 条
- 词表外概念建议：读 suggested_tags.json

---

## 下一步入口

```bash
python tag_real.py --prepare --limit 20
# 读图，输出 batch_results_NNN.json
python tag_real.py --apply-batch
```

或用 run.bat：
```
run prepare 20
run apply
```
