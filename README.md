# Eagle 素材库自动打标工具

基于 LLM（mimo）的 [Eagle](https://eagle.cool/) 素材库批量打标系统。通过视觉模型自动为图片素材生成结构化标签，写回 Eagle。

## 当前状态

- **词表版本**：v2.5（366 标签 / 23 前缀）
- **已处理**：970 / 20,378 张（4.76%）
- **架构版本**：v2.0 + a1 阶段完成（rules.json 单一真相源，前缀从 tags.json 自动派生）

## 标签体系

23 个前缀覆盖设计素材的多个维度：

| 前缀 | 说明 | 示例 |
|------|------|------|
| 类- | 素材类型 | 角色设定、概念图、UI |
| 风- | 视觉风格 | 赛博朋克、卡通、写实3D |
| 格- | 游戏美学锚点 | 光环、死亡搁浅、赛博朋克2077 |
| 题- | 主题/题材 | 机甲、末日、太空 |
| 代- | 文化时空背景 | 中式、日式、维多利亚、巴洛克 |
| 服- | 服装形制 | 机甲、铠甲、西装、长袍 |
| 姿- | 人物姿态 | 站立、奔跑、战斗、飞行 |
| 职- | 人物身份 | 战士、法师、刺客、工匠 |
| 件- | 机械/载具形态 | 铠甲、飞行器、武器 |
| 载- | 载具子类细分 | 战斗机甲、赛车、飞船 |
| 域- | 物理活动域 | 陆、空、海、太空 |
| 派- | 设计流派/主义 | 极简主义、蒸汽波、赛博格 |
| ... | 共 23 类 | 完整词表见 `config/tags.json` |

## 快速开始

### 1. 环境准备

```bash
pip install -r requirements.txt
```

### 2. 配置 API Key

复制 `.env.example` 为 `.env`，填入你的 mimo API Key：

```bash
cp .env.example .env
```

```env
MIMO_API_KEY=your_key_here
MIMO_BASE_URL=https://token-plan-cn.xiaomimimo.com/v1
MIMO_MODEL=mimo-v2.5
```

### 3. 确保 Eagle 运行中

Eagle API 默认地址：`http://localhost:41595/api`

### 4. 运行

```bash
# 准备下一批待处理素材（默认 20 张）
python tag_real.py --prepare --limit 20

# 批量打标并写回 Eagle（自动读取 pending.json + 调 LLM + 写回）
python tag_real.py --apply-batch --size 20

# 单张测试（不写回 Eagle）
python tag_real.py --test-llm <ITEM_ID>

# 重跑失败项
python tag_real.py --retry-failed 054

# 生成 batch 简报
python tag_real.py --batch-report 054

# 同步派生文件（STATE.md / HANDOFF.md）
python tag_real.py --sync
```

## 启动与停止

- **启动**：双击 `run.bat`（独立 cmd 窗口，不要从 Claude Code 启动）
- **停止**：在 cmd 窗口按 `Ctrl+C`；或紧急情况双击 `kill_all.bat`
- **重启电脑后**：直接双击 `run.bat` 即可，run.bat 会自动清理失效的 `data/run.lock`
- **单实例保护**：run.bat 启动时写入 PID 到 `data/run.lock`，已有循环在跑时会拒绝启动

## 异常处理

### exceptions.json

超时或异常的 item 会写入 `data/exceptions.json`，schema：

```json
{
  "id": "item_id",
  "reason": "mimo_timeout",
  "timestamp": "2026-05-07T13:50:56Z",
  "batch": 2974,
  "extra": {}
}
```

### reason 取值

| reason | 说明 |
|--------|------|
| `mimo_timeout` | mimo API 单任务超时（90s），Pool 重建后跳过该项 |
| `mimo_error` | mimo API 返回异常（非超时） |
| `vocab_mismatch` | mimo 返回的标签不在词表中 |
| `eagle_api_error` | Eagle API 写回失败 |
| `other` | 其他未分类异常 |

### 容错机制

- 单张图超时不影响整个 batch，超时项写入 exceptions.json 后跳过，Pool 重建继续处理剩余项
- 历史问题与修复方案详见 [docs/BUG_LEDGER.md](docs/BUG_LEDGER.md)

## 项目结构

```
eagle-organizer/
├── tag_real.py          # 主脚本
├── rules_engine.py      # 规则引擎
├── run.bat              # 循环启动器（带 PID 锁）
├── kill_all.bat         # 紧急停止（杀进程树）
├── config/
│   ├── tags.json        # 标签词表（v2.5, 367 标签）
│   ├── rules.json       # 标签规则
│   ├── workflow.json    # 工作流配置
│   ├── preferences.json # 偏好设置
│   ├── CHANGELOG.md     # 词表变更日志
│   └── prompts/         # LLM prompt 模板
├── data/                # 运行时数据（git 忽略）
│   ├── progress.json    # 进度与断点
│   ├── exceptions.json  # 异常记录
│   ├── pending.json     # 当前批次待处理
│   └── batches/         # batch 结果归档
├── derived/             # 自动派生文件
│   ├── CLAUDE.md
│   ├── STATE.md
│   └── HANDOFF.md
├── docs/
│   └── BUG_LEDGER.md    # BUG 台账
├── archive/             # 历史归档
└── reports/             # 测试与 batch 报告（git 忽略）
```

## 关键设计

- **单一真相源**：`config/` 存放所有配置，`derived/` 自动派生；已知前缀从 `tags.json` 自动派生（`get_known_prefixes`），新增前缀无需改代码
- **排异规则（a1 阶段完成）**：排异前缀已从 `tag_real.py` 硬编码迁移到 `config/rules.json`，双轨校验通过
- **断点恢复**：每 50 张自动检查点，支持从中断处继续
- **限速与重试**：~80 RPM 限速，429/5xx 指数退避重试
- **人工抽检**：支持 `--test-llm` 单张测试，结果写入 `reports/` 供审核

## License

Private
