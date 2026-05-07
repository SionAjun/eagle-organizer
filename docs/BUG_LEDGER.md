# BUG 台账

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
