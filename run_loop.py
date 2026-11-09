"""主线 0 持续跑批循环 - 带子进程硬超时防护。"""
import subprocess, sys, time, signal, os

SCRIPT = os.path.join(os.path.dirname(__file__), "tag_real.py")
BATCH_TIMEOUT = 300  # apply-batch 单批超时秒数

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
        run(["--prepare", "--limit", "20"])

        ts = time.strftime("%H:%M:%S")
        print(f"[{ts}] === apply-batch (timeout {BATCH_TIMEOUT}s) ===")
        rc = run(["--apply-batch", "--size", "20", "--workers", "5"], timeout=BATCH_TIMEOUT)
        if rc == -1:
            print(f"[{time.strftime('%H:%M:%S')}] ⚠️ apply-batch 超时，跳过继续下一轮")
        elif rc != 0:
            print(f"[{time.strftime('%H:%M:%S')}] ⚠️ apply-batch exit {rc}，继续下一轮")

if __name__ == "__main__":
    main()
