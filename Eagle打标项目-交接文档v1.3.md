# Eagle 素材库自动化打标项目 — 对话交接文档 v1.3
> 对话交接 v1.3 | 替代 v1.2
> 生成于 2026-04-26 | 进度快照：220 / 20378（1.08%）| 词表 v2.1

---

## 给读到这份文档的 Claude 的元指令（必读）

你是这个长期项目的「决策 + 指令产出」端，**不参与视觉判图**。

### 三方协作分工
| 角色 | 做什么 | 不做什么 |
|---|---|---|
| **用户** | 决定方向、审 batch_results、改 /config/、跨端中转 | 不再手动同步派生文件 |
| **你（对话 Claude）** | 出指令、审质量、设计规则、改 /config/ 草案 | **不看图打标**（除非用户主动要求二次审） |
| **Claude Code** | 看图打标、跑脚本、写派生文件 | 不擅自改 /config/ |

### 你和 Claude Code 不直接通信
所有跨端动作经用户中转：
你 → 用户（代码块指令）→ 用户复制 → Claude Code
Claude Code → 用户（截图/输出）→ 用户贴回 → 你
这是特性不是 bug——用户作为审核者把所有动作过一遍眼。

### 输出风格
- 命令一律放代码块，可直接粘贴
- 不复述已知背景
- 进度汇报简短中文 + 必要表格
- 不主动炫技、不催进度

---

## 1. 项目身份

| 项 | 值 |
|---|---|
| 用户身份 | 游戏美术 / 概念设计师 |
| 素材库 | Eagle 4.0 (Build 20250627)，20378 张 |
| 库路径 | `D:\杂项\素材.library` |
| 工作目录 | `C:\GAME 2333\game\Claud cod\eagle-organizer\`（含空格，shell 命令必须用引号） |
| 当前进度 | 220 / 20378（1.08%） |
| 主脚本 | tag_real.py（~1990 行）|
| 词表 | tags.json v2.1，227 标签，15 前缀 |
| 批次大小 | BATCH_SIZE = 20 |
| 检查点 | 每 50 张自动 |

---

## 2. 当前协作工作流（v1.3 修订）
用户 prepare → Claude Code 看图打标 → batch_results.json
→ 用户审或贴给对话 Claude 审 → apply-batch（含词表过滤兜底）
→ 自动 checkpoint → STATE.md 动态从 tags.json 重写

**关键约束**：
- 标签严格从 tags.json 选，词表外写入 suggested
- apply-batch 有词表过滤兜底（即使 LLM 错给词表外标签，写不进 Eagle）
- 写回 Eagle 前合并旧标签，不覆盖手动标签
- 24h 内新素材自动跳过
- 一张图只做一次视觉分析

### 2.1 异常素材挂起机制
判图遇到极度模糊 / 无意义占位图 / 无法归入现有体系：
- `tags_to_add: []`，回复正文标注 `挂起：item_id（原因）`
- 累计达 20 张时提醒用户集中清理

---

## 3. 词表 v2.1（227 标签 / 15 前缀）
类(17) 题(19) 风(13) 格(21) 版(9) 氛(14)
光(18) 镜(15) 构(10) 场(16) 角(18) 物(15)
材(24) 色(12) 教(6)

最新关键变更（v2.1 相对 v2.0.2）：
- 新增「格-」21 个游戏美学锚点
- 新增「版-」9 个排版结构
- 废除：风-黑魂（迁 格-魂系）、风-米哈游

排异规则：
- 类-UI / 类-排版 / 类-实景参考：屏蔽 光/镜/氛/场
- 类-UI / 类-排版：放行 格/版（v2.1 通道）

---

## 4. 用户设计偏好（协作核心）

**用户是概念设计师，翻图是为了"偷美学"，不是研究 UI 功能。**

| 心理活动 | 词表对应 |
|---|---|
| "这像哪个游戏的美学" | **格-**（主检索入口） |
| "这是什么排版结构" | 版- |
| "这是什么绘画技法" | 风-（纯技法，不再含作品名） |

**绝不要建** `面-HUD/面-菜单` 这种 UI 功能拆解维度。
**食物素材**仅 1 个粗粒度标签，按现状处理即可。

---

## 5. 已完成关键节点

| 日期 | 节点 | 摘要 |
|---|---|---|
| 04-22~04-24 | 早期阶段 | v1.0→v2.0 词表与脚本重构（13→14 前缀，398→199 标签） |
| 04-25 | v2.1 词表 | 新增格/版前缀，227 标签，15 前缀 |
| 04-25 | 自动化清理 | --cleanup 命令，checkpoint/apply-batch 钩子 |
| 04-25 | 200 张 v2.1 回溯 | 全量补打 格-/版-，覆盖率 42% |
| **04-26** | **架构修正 P0** | **STATE.md 模板从硬编码 v1.0 改为动态读 tags.json** |
| **04-26** | **打标自检规则** | **强制自检词表存在性，含具体反例** |

---

## 6. 关键命令 cheatsheet

```bash
# 主流程
python tag_real.py --prepare --limit 20
python tag_real.py --apply-batch
python tag_real.py --checkpoint

# 自动化清理
python tag_real.py --cleanup --dry-run
python tag_real.py --cleanup

# 回溯（v2.1 已用过，未来词表升版时再用）
python tag_real.py --build-ge-queue
python tag_real.py --triage
python tag_real.py --apply-batch --batch ge_NN
```

---

## 7. 已踩过的坑（核心 4 条，完整列表见 docs/pitfalls.md）

| 坑 | 解决 |
|---|---|
| 系统代理劫持 localhost | `urllib.request.ProxyHandler({})` 绕过 |
| Eagle API limit 静默截断 | 统一 limit=1000 |
| `/api/v2/` 不存在（Eagle 4.0） | 全用 `/api/` |
| **STATE.md 模板硬编码过期词表** | **2026-04-26 已修复，现从 tags.json 动态读** |

---

## 8. 待处理清单（不主动 surface，用户问才列）

| # | 事项 | 优先级 |
|---|---|---|
| ① | **阶段 2 架构重构**：抽 /config/ 单一真相源 + --sync 命令派生 STATE.md / CLAUDE.md / HANDOFF.md | **高** |
| ② | suggested_tags 集中审核（含本批新增 4 条：类-场景设定、类-角色设定、构-俯视、题-末世） | 中 |
| ③ | 全自动化方案 P2：API 直连打标 | 大改造 |

---

## 9. 协作行为约束

- 不主动提醒待处理事项，仅用户问"还有什么要处理"时才列第 8 节
- 命令放代码块、判图结果给完整 JSON、汇报简短表格
- 批次大小 20，质量 OK 时保持
- **绝不亲自看图打标**——视觉判断由 Claude Code 全自动执行

---

## 10. 文档维护规则

### 10.1 何时生成新版本
- 完整迭代结束 + 上下文紧张
- 用户主动说"对话太长了"
- 累计超过 ~30 轮有效互动

### 10.2 生成流程
1. 读 STATE.md / REPORT.md / tags.json / progress.json 核对所有数字
2. 整体重写为 v(N+1)，章节结构不变
3. 输出完整 markdown 代码块
4. 头部标注"对话交接 v(N+1) | 替代 v(N)"

### 10.3 体积控制
- 时间线 > 10 行：折叠为单行汇总
- 踩坑 > 8 条：归档到 docs/pitfalls.md，本文档只留 3 个高频坑

### 10.4 绝不能丢失
- 第 2 节工作流（含三方分工）
- 第 4 节用户偏好
- 第 9 节行为约束

---

## 11. ⚠️ 未完成开始的工作

### 上一对话停在哪里
2026-04-26 batch_011（20 张）打标完成并 apply-batch 成功。

发现 Claude Code 在 batch_011 的 6 张图中错用 4 个词表外标签
（类-场景设定×2、类-角色设定、构-俯视×2、题-末世），但
**apply-batch 词表过滤兜底已拦截，Eagle 库未被污染**。

已修：STATE.md 模板追加"强制自检规则"段，含具体反例。
已记：4 个词表外概念追加到 suggested_tags.json。

### 下一步：B-6 阶段 2 架构重构

新对话开场后，用户会让你启动**阶段 2 重构**：抽 /config/ 单一真相源
+ --sync 命令派生 STATE.md / CLAUDE.md / HANDOFF.md。

完整指令草案保存在本文档第 12 节，新对话开场即可使用。

阶段 2 完成验收标准：
1. /config/tags.json /config/rules.json /config/preferences.json 等
2. python tag_real.py --sync 重新派生所有派生文件
3. 派生文件头部带 `<!-- AUTO-GENERATED FROM /config/. DO NOT EDIT -->`
4. 改 config 测试标签 → --sync → 派生文件全部更新

### 阶段 2 完成后回归主线
继续 prepare → 打标 → apply-batch 流程，每 1000 张做一次
suggested 集中审核 + 词表升版评估。

---

## 12. 阶段 2 重构指令（新对话开场即可粘贴给 Claude Code）
任务：实施 config + derived 单一真相源架构
—— 一、目录与文件迁移 ——
mkdir config derived archive/derived_legacy
移动到 config/：

tags.json → config/tags.json
新建 config/rules.json：把 R1~R10 / S1~S4 / U1 从 tag_real.py 抽出
新建 config/workflow.json：BATCH_SIZE、checkpoint 频率、24h 保护期
新建 config/preferences.json：用户设计偏好（v1.3 文档第 4 节）
新建 config/CHANGELOG.md：人写一行的变更日志，倒序

旧 STATE.md / HANDOFF.md / REPORT.md 移到 archive/derived_legacy/。
—— 二、新增 --sync 命令 ——
python tag_real.py --sync 逻辑：

读 config/ 全部文件
重新渲染 derived/STATE.md、derived/CLAUDE.md、derived/HANDOFF.md
每个派生文件头部写：
<!-- AUTO-GENERATED FROM /config/. DO NOT EDIT.
     Last sync: {timestamp} from tags.json v{version} -->

--checkpoint 和 --apply-batch 完成后自动调 --sync

—— 三、抽出规则 ——
把 tag_real.py 里 _triage_one() 等函数中的规则字符串
全部移到 config/rules.json，函数改为读 JSON。
rules.json 结构：
{
"version": "v2.1.1",
"rules": [
{"id": "R1", "if": {"contains": ["题-赛博朋克"]},
"candidates_ge": ["格-赛博朋克2077", "格-命运2", "格-控制"]},
...
],
"skips": [
{"id": "S1", "if": {"contains_prefix": "格-"}, "skip": "格-"},
...
]
}
—— 四、CLAUDE.md 内容 ——
新建 derived/CLAUDE.md，由 --sync 派生，包含：

项目身份（从 config 读）
启动顺序（固定模板）
标签选择优先级（格-/版- 加权）
规则表（从 rules.json 渲染）
强制自检规则（含反例）
输出格式
安全约束

放在项目根目录的副本（Claude Code 启动时会读 CLAUDE.md）。
—— 五、HANDOFF.md 自动化 ——
HANDOFF.md 由 --sync 派生：

当前进度（progress.json 动态读）
当前词表版本与变更摘要（CHANGELOG 末尾 5 条）
用户偏好（preferences.json）
已知坑（手维护字段，有上限提示）

新增 --handoff-snapshot 命令：把 HANDOFF.md 复制到
archive/handoffs/HANDOFF_{timestamp}.md。
—— 六、跑通验证 ——

python tag_real.py --sync
打开 derived/CLAUDE.md / derived/STATE.md / derived/HANDOFF.md
三个文件全部带 AUTO-GENERATED 头
三个文件的词表数字都从 tags.json 实时读
改 config/tags.json（加测试标签）→ --sync → 三个派生文件全部更新

完成后输出：

三个派生文件的当前路径
sync 一次的耗时
是否需要在 .claude/settings.json 把 config/ 加为只读保护


---

## 附：冷启动流程

新对话的 Claude 读完本文档后，**立即按以下三步执行，不寒暄**：

**Step 1** — 告知用户：
> 已读完交接文档 v1.3，准备就绪。

**Step 2** — 输出可粘贴指令，让本机加载最新状态：
请把以下文件的当前内容贴回对话：

tags.json（最新词表）
STATE.md（当前进度与待办）
progress.json 末尾 50 行（确认最近批次）
suggested_tags.json（含本批新增 4 条待审）


**Step 3** — 询问：
> 状态加载完成后，从哪里开始？建议优先级：
> A. 启动阶段 2 重构（指令已在文档第 12 节）
> B. 继续主线打标
> C. 其他

**进度数字（220/20378、v2.1）仅作历史快照**，以 Step 2 拉回的实际文件为准。