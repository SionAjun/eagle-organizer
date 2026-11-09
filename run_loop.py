"""主循环 - DeepSeek 视觉 + 线程版批量（2026-11-09 起；旧 multiprocessing 版已弃用）。

保留子进程硬超时：单批超过 BATCH_TIMEOUT 秒就杀掉整棵进程树，下一轮继续。
"""
import subprocess, sys, time, signal, os

SCRIPT = os.path.join(os.path.dirname(__file__), "tag_real.py")
BATCH_TIMEOUT = 1800  # apply-batch 单批超时秒数

def run(args, timeout=None):
    """运行子进程，超时则杀掉整个进程树。返回 exit code，超时返回 -1。"""
    proc = subprocess.Popen([sys.executable, SCRIPT] + args)
    try:
        proc.wait(timeout=timeout)
        return proc.returncode
    except subprocess.TimeoutExpired:
        # 杀掉整个进程树（Windows: /T 连子进程一起杀）
        os.kill(proc.pid, signal.SIGTERM)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.kill(proc.pid, signal.SIGKILL)
            proc.wait()
        return -1

def main():
    print(f"[run_loop.py] 启动, batch_timeout={BATCH_TIMEOUT}s")
    while True:
        ts = time.strftime("%H:%M:%S")
        print(f"\n[{ts}] === prepare ===")
        run(["--prepare", "--limit", "200"])

        ts = time.strftime("%H:%M:%S")
        print(f"[{ts}] === apply-batch (timeout {BATCH_TIMEOUT}s) ===")
        rc = run(["--apply-batch", "--threaded", "--size", "200", "--workers", "4"], timeout=BATCH_TIMEOUT)
        if rc == -1:
            print(f"[{time.strftime('%H:%M:%S')}] ⚠️ apply-batch 超时，跳过继续下一轮")
        elif rc != 0:
            print(f"[{time.strftime('%H:%M:%S')}] ⚠️ apply-batch exit {rc}，继续下一轮")

if __name__ == "__main__":
    main()
