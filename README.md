# Eagle 素材库自动打标工具

用视觉模型给 Eagle 素材库批量打结构化标签，写回 Eagle。标签体系 23 前缀 / 382 标签，
面向"翻图偷美学"的检索习惯（格- 游戏锚点优先，版- 次之）。

## 当前状态（2026-11-09）

| 项 | 值 |
|---|---|
| 词表 | `config/tags.json` **v2.7.0**，382 标签 / 23 前缀 |
| 库总量 | **22,692** 张（Eagle 4.0.0，库路径 `S:\02_Reference_参考图库\素材.library`） |
| 打标链路 | **DeepSeek 视觉模式**：`deepseek-flash`（支持 image 输入），无 mimo 依赖 |
| 并发方式 | 线程池（`--apply-batch --threaded`），逐条落盘、日志实时 |
| 词表扩展 | `suggested` count≥3 **自动晋升**（同义词映射 + 黑名单，见 `PROMOTE_*`） |

> **历史节点**
> - 2026-08-12 mimo API key 过期，agent 手动读图模式顶了一段时间
> - 2026-10-26 素材库从 `D:\杂项\素材.library`（USB 机械盘，I/O 阻塞导致 Eagle 黑屏）迁到 S 盘
> - 2026-11-09 接入 DeepSeek 视觉，恢复无人值守跑批；同批修掉库路径硬编码、总量失真、
>   multiprocessing 卡死等 7 项隐患

## 快速开始

```bash
pip install -r requirements.txt        # openai / python-dotenv / Pillow

# 0. 探活：key + 模型 + 图像输入
python tag_real.py --probe-llm

# 1. 无人值守跑完所有待办（prepare + 线程版写回，pending 清空即停）
python -u run_ai_loop.py --limit 200 --workers 4

# 2. 只跑一批
python tag_real.py --prepare --limit 200
python tag_real.py --apply-batch --threaded --size 200 --workers 4

# 3. 词表晋升 / 刷新派生文件
python tag_real.py --promote-suggested
python tag_real.py --sync
```

配置在 `.env`（已被 gitignore）：

```ini
VISION_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-...
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-flash
DEEPSEEK_REASONING_EFFORT=low
VISION_MAX_TOKENS=3000
VISION_MAX_EDGE=768        # 原图先降采样到这个长边再送模型
VISION_WORKERS=4
AUTO_PROMOTE=1             # 1=每批结束自动晋升 suggested
```

## 主脚本命令

| 命令 | 作用 |
|---|---|
| `--probe-llm` | 视觉链路探活（/models + 真发一张图） |
| `--prepare --limit N` | 取未处理素材写 `data/pending.json`（库路径预检，路径错会中止而不是烧进度） |
| `--apply-batch --threaded` | 线程池打标 + 写回 Eagle（**推荐**） |
| `--apply-batch` | 旧 multiprocessing 版（Windows 上有卡死/孤儿进程史，仅兼容保留） |
| `--apply-agent <file>` | 写回 agent 手工读图产出的 JSON（同样走词表校验/排异/合并） |
| `--test-llm <id>` | 单张测试，报告落 `reports/test_llm_<id>.json`，不动进度 |
| `--promote-suggested` | 把 count≥3 的 suggested 晋升进词表 |
| `--checkpoint` / `--sync` | 手动检查点 / 从 config 重新生成 `derived/` 三件套 |
| `--cleanup` | 归档旧版本备份与已完成的 review 文件 |

历史模块（回溯、格- 分诊、人工基线）保留在脚本里，当前流程不再使用。

## 打标规则（要点）

- **格-**（最高权重）：视觉风格明确对应某游戏就补，拿不准不补；候选缩窄 R1–R8 见
  `rules_engine.py` / `config/prompts/格.txt`
- **版-**：`类-UI` / `类-排版` 必判
- **排异**：`类-UI` / `类-排版` 屏蔽 镜/光/氛/场/构/件/载/域；`类-拆解图` 屏蔽 氛/光；
  `类-像素画` 屏蔽 材 —— 规则存在 `config/rules.json`，由 `rules_engine.py` 双轨校验
- **词表硬约束**：只能输出 `config/tags.json` 里逐字存在的标签；词表外概念进
  `suggested`，由晋升机制决定是否进表
- 一图一分析；写回前合并旧标签，不覆盖手工标签

## 数据与账本

| 文件 | 说明 |
|---|---|
| `data/progress.json` | 核心进度：`processed_ids` / records / 批次号 / 统计 |
| `data/pending.json` | 当前批次待处理（全部落地后才归档到 `archive/batches/`） |
| `data/batches/batch_results_NNN.json` | 每批结果，线程版逐条实时写入 |
| `data/exceptions.json` | 运行时异常（mimo 时代死账已归档到 `archive/exceptions/`） |
| `data/suggested_tags.json` | 词表外候选 + 计数（晋升后自动移除） |
| `derived/` | `--sync` 生成的 CLAUDE / STATE / HANDOFF，新会话入口 |

## MCP 服务（mcp-server/）

把 Eagle 的查询、看图、加标签做成 MCP 工具，供 Claude Desktop / Claude Code / DSH 调用：

- 上游 `tuki0918/eagle-mcp-server`（fastmcp-stdio 分支，MIT），本地新增
  `find_items`（精简字段搜索）、`view_items`（1–8 张 640px 预览）、
  `add_item_tags`（只增不替换）
- 关掉 `move_item_to_trash` 等破坏性工具
- 安装：`mcp-server/install_eagle_mcp.bat`（装 uv/依赖 + 写 Claude Desktop 配置）
- 库路径由 Eagle API 动态读取，不受磁盘迁移影响

## 已知坑

见 [docs/BUG_LEDGER.md](docs/BUG_LEDGER.md)（BUG-001 ~ BUG-010）。最常踩的：

1. 系统代理劫持 localhost → 脚本统一 `ProxyHandler({})`
2. Eagle API 无总数字段 → 单次 `limit=25000` 拉全量
3. `btime=0` 的老素材 → 用 `modificationTime` 判 24h 保护
4. **multiprocessing 版批量会静默卡死** → 用 `--threaded`
5. 坏 key 会整批空转且写黑名单 → 跑批前 `--probe-llm`，0 成功批次不归档不拉黑

## License

Private
