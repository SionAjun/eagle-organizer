<!-- AUTO-GENERATED FROM /config/. DO NOT EDIT.
     Last sync: 2026-05-09 01:08:00 from tags.json v2.5.2 -->

# Eagle 打标项目 — 新对话开场交接文档


⚠️ exceptions.json 累计 406 条，建议集中处理

> 新会话开始时只需粘贴本文件，无需其他文档。

---

## 当前进度

- 已处理：**20567 / 20378** 张（100.93%）
- 批次号：3305
- 最后 item_id：`7c367eb5-37c6-43e4-91ad-4ef17df62261`

---

## 当前词表版本与近期变更

tags.json v2.5.2，367 标签 / 23 前缀

最近 5 条变更：
- 删除 rules_engine.py 的 normalize_synonyms 函数（定义存在但主流程从未调用）
- 删除 config/rules.json 的 ge_synonyms 字段
- 决策依据：实证检查 suggested_tags.json 后发现 0 条匹配场景——LLM 没有同义词归一需求，词表外标签都是真实词表缺失（应入表评审）而非简写
- 真出现简写需求时，5 行代码可重写；保留死代码反而是契约谎言
- 未受影响：filter_tags_by_primary 钩子保留（B+ 方案，未来 stage-1 激活时使用）

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

- suggested_tags.json count≥3 待审：16 个
- exceptions.json 累计：406 条
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
