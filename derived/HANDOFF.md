<!-- AUTO-GENERATED FROM /config/. DO NOT EDIT.
     Last sync: 2026-08-15 13:41:32 from tags.json v2.5.2 -->

# Eagle 打标项目 — 新对话开场交接文档


⚠️ exceptions.json 累计 78 条，建议集中处理

> 新会话开始时只需粘贴本文件，无需其他文档。

---

## 当前进度

- 已处理：**21818 / 20605** 张（105.89%）
- 批次号：3320
- 最后 item_id：`MP8IULGWIWFFZ`

---

## 当前词表版本与近期变更

tags.json v2.5.2，367 标签 / 23 前缀

最近 5 条变更：
- mimo API key 过期且不续费（实测 `GET /v1/models` 返回 401 `Invalid API Key`），200 张批次全部
- 新增 `--apply-agent <结果文件>`：把 agent 读图产出的标签写回 Eagle，不调任何 LLM API，复用
- 新增 `scripts/make_previews.py`：把 pending 素材压成长边 640px 预览图（单张读图成本约 1.6k → 500 token）
- 新增 `scripts/validate_agent_tags.py`：写回前校验词表合法性 + 排异冲突，并对前缀写错给出提示
- `derived/` 三份模板同步改写为 agent 模式入口，已知坑追加第 7 条

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
7. **mimo API 已停用**（2026-08-12 起）→ key 过期且不续费，`--apply-batch` 全批返回
   AuthenticationError → mimo_exhausted，看着像"跑完了"实际 0 成功。视觉打标改由
   agent 自己读图，走 `--apply-agent`，不要再启动 run.bat / run_loop.py

---

## 待处理清单（不主动 surface）

- suggested_tags.json count≥3 待审：18 个
- exceptions.json 累计：78 条
- 词表外概念建议：读 suggested_tags.json

---

## 下一步入口（agent 视觉模式 — mimo 已停用，勿走 --apply-batch）

```bash
# 1. 取待处理素材（一次可取 200）
python tag_real.py --prepare --limit 200

# 2. 生成降采样预览图（长边 640px，省 token）
python scripts/make_previews.py <预览目录>

# 3. agent 自己读 <预览目录> 里的图，按词表输出结果 JSON：
#    [{"item_id": "...", "tags_to_add": ["类-概念图", ...], "suggested": ["..."]}]

# 4. 写回前先校验词表 + 排异（挡住前缀写错这类问题）
python scripts/validate_agent_tags.py <结果文件>

# 5. 写回 Eagle（不调任何 LLM API）
python tag_real.py --apply-agent <结果文件>
```

结果文件可以分片（每片 20 条），`--apply-agent` 可重复调用，
pending 全部写回后才会自动归档。
