<!-- AUTO-GENERATED FROM /config/. DO NOT EDIT.
     Last sync: 2026-11-09 21:21:19 from tags.json v2.7.0 -->

# Eagle 打标项目 — 新对话开场交接文档


> 新会话开始时只需粘贴本文件，无需其他文档。

---

## 当前进度

- 已处理：**22700 / 22692** 张（100.04%）
- 批次号：3328
- 最后 item_id：`LJ2I7P2BUAD7L`

---

## 当前词表版本与近期变更

tags.json v2.7.0，382 标签 / 23 前缀

最近 5 条变更：
- 自动晋升 1 个标签（阈值 count>=3）
- + 格-原神（count=1726）
- 合计 382 标签 / 23 前缀
- 自动晋升 14 个标签（阈值 count>=3）
- + 镜-全身（count=421）

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
7. **mimo 已停用，改用 DeepSeek 视觉**（2026-11-09 起）→ `VISION_PROVIDER=deepseek` +
   `deepseek-flash`（支持 image 输入）。旧 `--apply-batch`（multiprocessing）在 Windows 上
   会静默卡死、输出全缓冲，一律用 `--apply-batch --threaded` 或 `run_ai_loop.py`
8. **库路径已从 D 盘迁到 S 盘**（2026-10-26）→ 代码不再硬编码，运行时按
   Eagle API → workflow.json 解析；`.claude/settings.json` 里的目录也已改指 S 盘
9. **multiprocessing.Pool 的 90s get 超时会反复重建 Pool** → 表现是进程活着但零输出，
   已由线程版替代；旧命令仅留兼容

---

## 待处理清单（不主动 surface）

- suggested_tags.json count≥3 待审：0 个
- exceptions.json 累计：2 条
- 词表外概念建议：读 suggested_tags.json

---

## 下一步入口（DeepSeek 视觉模式）

```bash
# 0. 探活：key + 模型 + 图像输入
python tag_real.py --probe-llm

# 1. 无人值守跑完整个待办（prepare + 线程版写回，pending 清空即停）
python -u run_ai_loop.py --limit 200 --workers 4

# 2. 单批手动：取数 → 线程版写回
python tag_real.py --prepare --limit 200
python tag_real.py --apply-batch --threaded --size 200 --workers 4

# 3. 词表晋升（每批结束已自动执行，可手动补跑）
python tag_real.py --promote-suggested

# 4. 刷新 derived/
python tag_real.py --sync
```

线程版逐条落盘：`data/batches/batch_results_NNN.json` 实时增长，`logs/run_ai2_*.log` 可 tail；
pending 全部落地才归档，中途失败保留 pending 供下一轮续跑。
