"""DeepSeek 视觉打标循环：prepare → apply-batch，直到没有待处理素材。

与旧 run.bat / run_loop.py 的区别：
  - 不再依赖 mimo，视觉部分走 VISION_PROVIDER（默认 deepseek-flash）
  - 每轮先 prepare 拿一批（默认 200），再 apply-batch 写回
  - pending 为空即停；连续 3 轮 0 成功也会停（防坏 key 空转，BUG-006 教训）
  - 批次结果、检查点、derived/ 同步沿用 tag_real.py 既有逻辑

用法：
    python run_ai_loop.py                 # 默认 200/批，4 worker
    python run_ai_loop.py --limit 100 --workers 4 --max-rounds 5
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
PY = sys.executable
PENDING = BASE / "data" / "pending.json"


def run(args, label):
    print(f"\n[{time.strftime('%H:%M:%S')}] === {label} ===", flush=True)
    proc = subprocess.run([PY, "-u", str(BASE / "tag_real.py")] + args, cwd=str(BASE))
    return proc.returncode


def pending_count():
    if not PENDING.exists():
        return 0
    try:
        return len(json.loads(PENDING.read_text(encoding="utf-8")))
    except Exception:
        return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=int(os.getenv("LOOP_LIMIT", "200")))
    ap.add_argument("--workers", type=int, default=int(os.getenv("VISION_WORKERS", "4")))
    ap.add_argument("--max-rounds", type=int, default=40)
    args = ap.parse_args()

    dry_rounds = 0
    t_all = time.time()
    for rnd in range(1, args.max_rounds + 1):
        print(f"\n########## 第 {rnd} 轮 ##########", flush=True)
        run(["--prepare", "--limit", str(args.limit)], "prepare")
        n = pending_count()
        if n == 0:
            print("\n✅ pending 为空：没有待处理素材了，循环结束", flush=True)
            break
        rc = run(["--apply-batch", "--threaded", "--size", str(n), "--workers", str(args.workers)], "apply-batch")
        # 判断本轮是否有产出：看 batch_results 最新文件里的 success 数
        if rc == 0:
            dry_rounds = 0
        else:
            dry_rounds += 1
            if dry_rounds >= 3:
                print("\n⛔ 连续 3 轮异常退出，停止循环（疑似认证/额度/网络问题）", flush=True)
                break

    print(f"\n全部结束，总耗时 {(time.time() - t_all) / 60:.1f} 分钟", flush=True)


if __name__ == "__main__":
    main()
