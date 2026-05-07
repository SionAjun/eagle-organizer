@echo off
setlocal

set LOCK=data\run.lock

if not exist %LOCK% (
  echo 未找到 %LOCK%，无锁可杀。
  echo 如需强制清理所有 python 进程: taskkill /F /IM python.exe
  exit /b 1
)

set /p PID=<%LOCK%
echo 杀掉进程树 PID=%PID% ...
taskkill /T /F /PID %PID%
del %LOCK%
echo 锁文件已删除。
exit /b 0
