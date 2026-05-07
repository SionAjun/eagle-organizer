@echo off
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
python tag_real.py --prepare --limit 20
if errorlevel 1 goto cleanup
python tag_real.py --apply-batch --size 20 --workers 5
if errorlevel 1 goto cleanup
timeout /t 2 >nul
goto loop

:cleanup
if exist %LOCK% del %LOCK%
echo 循环结束
exit /b 0
