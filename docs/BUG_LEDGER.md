# BUG 台账

## BUG-011: DeepSeek 探活被 response_format 反咬一口

- **发现日期**：2026-11-09
- **现象**：`--probe-llm` 报"视觉探活无返回"，日志只有一句
  `该端点不支持 response_format=json_object`，但同一 key 直接 POST 明明能过
- **根因**：DeepSeek 的 `response_format={"type":"json_object"}` 要求 prompt 里出现
  "json" 字样，否则 400 `Prompt must contain the word 'json'`。探活 prompt 写的是
  "只回一个词"，没提 JSON；而降级重试只给了一次预算（`max_retries=1`），第一次就耗光
- **修复**：探活 prompt 改成 "用 JSON 回答："；`call_deepseek` 重试轮次 +1（关 json 模式那次
  不占预算）；正式打标的 system prompt 本来就含"JSON 输出格式硬约束"，不受影响

---

## BUG-010: multiprocessing 批量在 Windows 静默卡死（零输出）

- **发现日期**：2026-11-09
- **现象**：`--apply-batch --size 200` 起了 5 个 worker，日志停在"启动 Pool(5)"，
  15 分钟没有任何输出；worker 进程 CPU 各 2 秒（= 只干了一两张），parent 空转
- **根因**：两层叠加
  1. `h.get(timeout=90)` 超时后重建 Pool 并重投未完成项，没有尝试计数上限 → 单张卡住会
     无限重建；实测 20:33:45 就重建过一轮，成为 20:31 那批的孤儿 worker
  2. 重定向到日志文件时 Python 全缓冲，主进程的进度打印一次都没落盘，看起来像"没跑"
- **修复**：新增 `cmd_apply_batch_threaded`（`--apply-batch --threaded`）：
  线程池 + `as_completed` + 逐条 `flush` 打印 + 逐条写 `batch_results`，
  HTTP 客户端自带 `VISION_TIMEOUT`，不再依赖 Pool 的 get 超时
- **验证**：6 张 24 秒完成、200 张批次日志实时可见；本机 4 线程 ≈ 3.5s/张

---

## BUG-009: records 账本对不平（少 1,983 条）

- **发现日期**：2026-11-09
- **现象**：`progress.total_processed` = 21,818，但 `records` 135 + `archive/records` 197 个文件
  19,700 条 = 19,835，缺口 1,983
- **根因**：早期版本按 `RECORDS_KEEP_RECENT` 截断 `records` 时没有同步归档，历史轮次直接丢账
- **处理**：不回填（原始 tags 已在 Eagle 侧，重算无意义），在台账登记口径：
  **进度以 `processed_ids` 为准，records 仅作近期审计样本**

---

## BUG-008: library_total 长期失真，派生文件算出 105.89% 完成度

- **发现日期**：2026-11-09
- **现象**：`workflow.json.library_total` 停在 20,605，实际库 22,692；
  `derived/STATE.md` 显示 "21818 / 20605（105.89%）"，新会话据此判断进度会直接跑偏
- **根因**：总量是 2026-05-12 手填的常量，之后库持续新增（21,925 → 22,692）没人改
- **修复**：`cmd_prepare` 每次拉全量后把实测条数回写 `workflow.json.library_total` 与
  `library_path`；`tag_real.py` 的 `LIBRARY_TOTAL` 只作兜底

---

## BUG-007: 库迁移后 tag_real.py 仍硬编码 D 盘，prepare 会把整库烧成 file_missing

- **发现日期**：2026-11-09（库迁移发生在 2026-10-26）
- **现象**：`LIB_PATH = Path("D:/杂项/素材.library")` 等 4 处硬编码；本机已无 D 盘。
  一旦执行 `--prepare`，每条素材都会走 `resolve_path()` 判不存在 →
  `append_exception(file_missing)` + `mark_exception_processed()`，
  **把 800+ 张正常素材写进 processed_ids 永久跳过**
- **根因**：2026-10-26 素材库从 USB 机械盘迁到 `S:\02_Reference_参考图库\素材.library`，
  迁移只改了 Eagle Settings，没动代码常量
- **修复**：
  1. 新增 `lib_path()`：环境变量 `EAGLE_LIBRARY_PATH` → Eagle API `/library/info` →
     `config/workflow.json` 三级解析，只认 `images/` 真实存在的候选
  2. `cmd_prepare` 加预检：前 20 个待处理素材若过半源文件缺失，直接中止且不写 progress
  3. `config/workflow.json`、`.claude/settings.json` 同步改指 S 盘
- **验证**：`--prepare --limit 3` 正常取到 S 盘路径；`--apply-batch --threaded` 6/6 写回成功

---

## BUG-006: mimo key 失效时整批静默空转，且会把好素材拉黑

- **发现日期**：2026-08-12
- **严重性**：高（数据污染风险）
- **现象**：`--apply-batch --size 200` 正常退出（exit 0），末尾打印 `✅ 批量完成：0 成功 / 200 失败`，
  `pending.json` 照常归档，`derived/` 照常同步。表面上"跑完了一批"，实际一张图都没读。
  日志开头是刷屏的 `[mimo] AuthenticationError 退避 1s/2s (attempt N/3)`。
- **根因**：两层问题叠加
  1. `.env` 里的 `MIMO_API_KEY` 已过期 —— 直接请求 `GET {MIMO_BASE_URL}/models` 返回
     `401 {"message": "Invalid API Key", "type": "invalid_key"}`。认证失败走的是和"模型拒答"
     完全相同的重试→`mimo_exhausted` 路径，脚本无法区分"key 坏了"和"这张图 mimo 不肯答"。
  2. `_scan_rejected_items()` 统计所有 `batch_results_*.json` 里的 `mimo_exhausted` 次数，
     达到 `MAX_REJECT_COUNT = 5` 就给 item 打 `mimo_拒绝` 标签并**永久跳过**。
     坏 key 连跑 5 轮 → 200 张正常素材被误判为"mimo 内容安全拒绝"，写进 Eagle 且不再重试。
- **诊断特征**（下次遇到照这个判）：
  - 整批耗时异常短：约 1.1 秒/张（正常读图是 10~20 秒/张）
  - `tokens: prompt=0 completion=0 cached=0` —— 根本没发生推理
  - `batch_results_NNN.json` 里 `failure_reason` 100% 是 `mimo_exhausted`（真实拒答不会这么整齐）
- **最终方案**：不修 mimo 链路（key 不续费了），改打标模式
  - 新增 `--apply-agent`，视觉部分由 agent 直接读图完成，彻底绕开 LLM API
  - 配套 `scripts/make_previews.py`（640px 预览，控 token）+ `scripts/validate_agent_tags.py`（写回前校验）
  - 把坏 key 产生的 `batch_results_3315.json` 移出 `data/batches/`（改名
    `archive/batches/batch_results_3315.auth_failed.json`），清掉 200 条拉黑计数
  - README / `derived/` 三份模板 / CHANGELOG 全部标注 mimo 停用，禁止再启 `run.bat` / `run_loop.py`
- **未修的已知缺陷**：`cmd_apply_batch` 仍然不会在跑批前做一次认证探活。若日后恢复 mimo，
  建议在 Pool 启动前先打一次 `/models` 或 `--test-llm`，401 直接中止而不是烧 200 张的重试。
- **涉及文件**：`tag_real.py`、`scripts/make_previews.py`、`scripts/validate_agent_tags.py`、
  `README.md`、`config/CHANGELOG.md`、`archive/batches/batch_results_3315.auth_failed.json`
- **验证方式**：`python scripts/validate_agent_tags.py <结果文件>` 全绿后
  `python tag_real.py --apply-agent <结果文件>`；本轮 200 张写回后回查 Eagle API，200/200 均有标签

---

## BUG-005: 缺失源文件 item 反复进入 pending 并刷爆 exceptions

- **发现日期**：2026-05-12
- **严重性**：中等
- **现象**：`LDB3BJU429160`（`Crystal.jpg`）在 `pending.json` 中反复出现，`apply-batch` 每轮进入 Pool 后报 `FileNotFoundError`，累计产生 331 条重复异常
- **根因**：`cmd_prepare` 只根据 Eagle item 元数据生成路径，没有在入队前检查源文件是否存在；`cmd_apply_batch` 也没有在启动 mimo/Pool 前过滤缺失文件，导致文件系统错误被归类为 `mimo_error`，且该 item 没有写入 `processed_ids`
- **最终方案**：
  - 新增 `file_missing` 运行时异常类型
  - `cmd_prepare` 在入队前检查 `resolve_path(item).exists()`，缺失时写入 exceptions、记录 progress，并跳过视觉打标
  - `cmd_apply_batch` 对已有 pending 再做一次缺文件过滤，写入 `skipped_missing_file` 批次结果，不启动 Pool
  - 将当前运行态中 `LDB3BJU429160` 标记为已处理异常，`pending.json` 从 20 条降至 19 条，331 条重复异常合并为 1 条 `file_missing`
- **涉及文件**：`tag_real.py`、`data/progress.json`、`data/pending.json`、`data/batches/batch_results_3305.json`、`data/exceptions.json`
- **验证方式**：`python scripts/test_missing_file_handling.py`，覆盖 prepare 和 apply-batch 两条路径

---

## BUG-004: bash while + timeout 命令不杀 Python 子进程

- **发现日期**：2026-05-07
- **严重性**：中等
- **现象**：`timeout 300 python tag_real.py --apply-batch` 超时后 Python 进程继续运行
- **根因**：Git Bash 的 `timeout` 只杀 bash 子 shell（PID 1），不传播 SIGTERM 到孙进程（Python）。bash 退出后 Python 变成孤儿
- **错误尝试**：
  - `timeout 300 python tag_real.py ...` — 只杀 bash，Python 继续跑
- **最终方案**：弃用 bash 循环，改用独立 `run.bat`（cmd 原生循环）
- **涉及文件**：`run.bat`
- **验证方式**：`tasklist | grep python` 确认超时后无残留进程

---

## BUG-003: multiprocessing 子进程树未清理干净

- **发现日期**：2026-05-07
- **严重性**：中等
- **现象**：`os.kill(pid, SIGTERM)` 杀掉主进程后，multiprocessing worker 进程继续运行
- **根因**：Windows 上 `os.kill(pid, signal.SIGTERM)` 不等价于 Unix 的 SIGTERM 传播。multiprocessing 的 spawn 模式创建独立进程，主进程退出后 worker 成为孤儿
- **错误尝试**：
  - `os.kill(proc.pid, signal.SIGTERM)` + `proc.wait(timeout=5)` — 只杀主进程，5 个 worker 全部残留
- **最终方案**：`taskkill /T /F /PID <pid>` 杀整个进程树（/T = tree）
- **涉及文件**：`kill_all.bat`
- **验证方式**：`wmic process where "name='python.exe'" get ProcessId` 确认无残留

---

## BUG-002: Claude Code background shell 孤儿进程堆积

- **发现日期**：2026-05-07
- **严重性**：严重
- **现象**：同一时间跑着 4 个 bash while 循环 + 6 个 Python 进程，互相抢资源
- **根因**：Claude Code 的 `run_in_background` 启动 bash 进程后，会话上下文压缩或切换时丢失 task 引用。旧循环变成孤儿继续跑，新循环又启动 → 指数堆积
- **错误尝试**：
  - 发现卡死直接启动新循环不杀旧的 — 旧的继续跑，新旧并行
  - 用 `taskkill /F /PID <pid>` 杀单个 bash — Python 子进程变孤儿
- **最终方案**：循环脱离 Claude Code，独立 cmd 窗口跑 `run.bat`，用 `data/run.lock` 文件锁保证单实例
- **涉及文件**：`run.bat`、`kill_all.bat`
- **验证方式**：启动 run.bat 后再次运行 run.bat 应提示"已有循环在跑"

---

## BUG-001: mimo API 偶发无限挂起

- **发现日期**：2026-05-07
- **严重性**：致命
- **现象**：apply-batch 子进程调用 mimo API 后永不返回，循环停摆。大约每 30-60 分钟发生一次
- **根因**：OpenAI Python SDK 的 `timeout` 参数控制 HTTP 层（连接超时 + 首字节超时），不保护已建立的 TCP 连接。当 mimo 服务端接受请求但挂起不返回响应时，SDK 会无限等待 — TCP 连接是"活的"（无 RST/FIN），read timeout 按数据块重置
- **错误尝试**：
  - `OpenAI(timeout=60.0)` — 只保护连接建立和首字节，不保护已建立连接的后续读取
  - `client.chat.completions.create(timeout=60)` — 同上，per-request timeout 也是 HTTP 层
  - `socket.setdefaulttimeout(90)` — 全局副作用，影响所有 urllib 请求（Eagle API 等），不可控
  - `threading.Timer` 强制关连接 — race condition，可能在写入 Eagle 时关掉连接导致数据损坏
- **最终方案**：`multiprocessing.Pool` + `apply_async` + `get(timeout=90)` 在主进程层硬超时。超时后 `pool.terminate()` + `pool.join()` 杀掉整个 worker 池，重建 Pool 继续处理剩余项。超时项写入 `data/exceptions.json`
- **涉及文件**：`tag_real.py`（cmd_apply_batch 函数）、`data/exceptions.json`
- **验证方式**：临时将 `POOL_TIMEOUT` 改为 1s，跑 batch 触发超时 → exceptions.json 写入成功 → Pool 重建后剩余项继续处理 → 主循环未死
