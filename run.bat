@echo off
REM 2026-11-09: 改用 DeepSeek + 线程版批量（旧 multiprocessing 版在 Windows 会静默卡死）
setlocal

set LOCK=data\run.lock

if exist %LOCK% (
  set /p OLDPID=<%LOCK%
  tasklist /FI "PID eq %OLDPID%" 2>nul | find "%OLDPID%" >nul
  if not errorlevel 1 (
    echo 已有循环在跑 PID=%OLDPID%
    echo 先执行: kill_all.bat 或 taskkill /T /F /PID %OLDPID%
    exit /b 1
  )
  del %LOCK%
)

python -c "import os;open(r'data\run.lock','w').write(str(os.getppid()))"
echo 循环启动，PID 写入 %LOCK%

:loop
python -u tag_real.py --prepare --limit 200
if errorlevel 1 goto cleanup
python -u tag_real.py --apply-batch --threaded --size 200 --workers 4
if errorlevel 1 goto cleanup
timeout /t 2 >nul
goto loop

:cleanup
if exist %LOCK% del %LOCK%
echo 循环结束
exit /b 0
