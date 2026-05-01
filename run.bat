@echo off
if "%1"=="prepare" python tag_real.py --prepare --limit %2
if "%1"=="apply"   python tag_real.py --apply-batch && python tag_real.py --handoff-snapshot && python tag_real.py --sync
if "%1"=="sync"    python tag_real.py --sync
if "%1"=="snap"    python tag_real.py --handoff-snapshot
if "%1"=="full"    python tag_real.py --prepare --limit %2 && echo ====== 上传 batch_results.json 后再跑 run apply ======
