"""
Eagle 素材库批量打标签 —— dry_run 骨架脚本
实际打标签逻辑尚未接入；本版只模拟处理流程，验证分页/断点续跑正确性。
"""

import argparse
import json
import logging
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# ── 路径常量 ──────────────────────────────────────────────────────────────────
BASE_DIR        = Path(__file__).parent
PROGRESS_FILE   = BASE_DIR / "progress.json"
SUGGESTED_FILE  = BASE_DIR / "suggested_tags.json"
TAGS_FILE       = BASE_DIR / "tags.json"
LOGS_DIR        = BASE_DIR / "logs"

EAGLE_API       = "http://localhost:41595/api"
PAGE_LIMIT      = 1000          # 每页拉取数量
PROTECTION_HOURS = 24           # 新素材保护期（小时）
CHECKPOINT_EVERY = 10           # 每处理多少张写一次进度
INCREMENTAL_STOP = 20           # 增量模式：连续已处理多少张停止

# ── Eagle API（绕过系统代理） ──────────────────────────────────────────────────
_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

def eagle_get(path: str) -> dict:
    url = EAGLE_API + path
    with _opener.open(url, timeout=30) as r:
        return json.loads(r.read())

# ── 进度文件 ──────────────────────────────────────────────────────────────────
def load_progress() -> dict:
    if PROGRESS_FILE.exists():
        return json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
    return {"processed_ids": [], "last_run_time": None,
            "total_processed": 0, "tag_version_used": {}}

def save_progress(prog: dict) -> None:
    prog["last_run_time"] = datetime.now(timezone.utc).isoformat()
    PROGRESS_FILE.write_text(
        json.dumps(prog, ensure_ascii=False, indent=2), encoding="utf-8"
    )

# ── 日志 ──────────────────────────────────────────────────────────────────────
def setup_logging() -> logging.Logger:
    LOGS_DIR.mkdir(exist_ok=True)
    ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
    log = logging.getLogger("eagle_tagger")
    log.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    fh  = logging.FileHandler(LOGS_DIR / f"run_{ts}.log", encoding="utf-8")
    fh.setFormatter(fmt)
    ch  = logging.StreamHandler()
    ch.setFormatter(fmt)
    log.addHandler(fh)
    log.addHandler(ch)
    return log

# ── 分页拉取（核心） ──────────────────────────────────────────────────────────
def iter_items(log: logging.Logger):
    """
    按添加时间倒序分页拉取所有素材。
    退出条件：连续 2 页返回空数组（防单页异常误判）。
    """
    offset       = 0
    empty_streak = 0

    while True:
        path = f"/item/list?limit={PAGE_LIMIT}&offset={offset}"
        log.debug(f"请求分页 offset={offset}")
        try:
            data = eagle_get(path).get("data", [])
        except Exception as e:
            log.warning(f"分页请求异常 offset={offset}: {e}，跳过本页继续")
            empty_streak += 1
            if empty_streak >= 2:
                log.info("连续 2 页异常/空结果，停止分页")
                break
            offset += PAGE_LIMIT
            continue

        if not data:
            empty_streak += 1
            log.debug(f"空页 (streak={empty_streak}) offset={offset}")
            if empty_streak >= 2:
                log.info("连续 2 页空结果，分页结束")
                break
        else:
            empty_streak = 0   # 有数据则重置连续空页计数
            for item in data:
                yield item

        offset += PAGE_LIMIT

# ── 保护期判断 ────────────────────────────────────────────────────────────────
def is_protected(item: dict) -> bool:
    """添加时间在 24 小时内的素材跳过。"""
    btime_ms = item.get("btime", 0)
    age_hours = (time.time() - btime_ms / 1000) / 3600
    return age_hours < PROTECTION_HOURS

# ── 主处理函数（dry_run：只打印，不打标签） ───────────────────────────────────
def format_modtime(item: dict) -> str:
    mt = item.get("modificationTime", 0) or 0
    if mt == 0:
        return "[时间缺失]"
    return datetime.fromtimestamp(mt / 1000).strftime("%Y-%m-%d %H:%M")

def process_item_dry(item: dict, log: logging.Logger) -> None:
    item_id = item["id"]
    name    = item.get("name", "")
    mt_str  = format_modtime(item)
    log.info(f"[DRY] id={item_id}  modificationTime={mt_str}  name={name!r}")

# ── 入口 ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Eagle 素材标签 dry_run")
    mode   = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--full",        action="store_true", help="全量模式：扫描整个库")
    mode.add_argument("--incremental", action="store_true", help="增量模式：遇到连续 20 张已处理就停")
    parser.add_argument("--limit", type=int, default=0,
                        help="调试用：只处理前 N 张后停止（0=不限制）")
    args = parser.parse_args()

    log  = setup_logging()
    prog = load_progress()
    processed_set = set(prog.get("processed_ids", []))

    log.info(f"运行模式: {'full' if args.full else 'incremental'}")
    log.info(f"已记录处理数: {len(processed_set)}")
    if args.limit:
        log.info(f"调试限制: 最多处理 {args.limit} 张")

    # 本次运行统计
    session_count     = 0   # 本次处理数
    skip_protected    = 0   # 保护期跳过数
    skip_already      = 0   # 已处理跳过数
    consec_done       = 0   # 增量模式：连续已处理计数

    # 用于简报的首/末张记录
    first_item_info   = None

    for item in iter_items(log):
        item_id = item["id"]

        # ── 增量模式停止判断 ──
        if args.incremental:
            if item_id in processed_set:
                consec_done += 1
                skip_already += 1
                if consec_done >= INCREMENTAL_STOP:
                    log.info(f"增量模式：连续 {INCREMENTAL_STOP} 张已处理，停止")
                    break
                continue
            else:
                consec_done = 0   # 遇到未处理的就重置

        # ── 全量模式：已处理直接跳过 ──
        elif item_id in processed_set:
            skip_already += 1
            continue

        # ── 保护期判断 ──
        if is_protected(item):
            skip_protected += 1
            log.debug(f"保护期跳过: {item_id}")
            continue

        # ── 调试限制 ──
        if args.limit and session_count >= args.limit:
            log.info(f"达到调试限制 {args.limit} 张，停止")
            break

        # ── 处理（dry_run：只打印） ──
        process_item_dry(item, log)

        # 记录第 1 张信息（用于简报）
        if session_count == 0:
            first_item_info = item

        # 更新进度
        processed_set.add(item_id)
        prog["processed_ids"].append(item_id)
        prog["total_processed"] = prog.get("total_processed", 0) + 1
        session_count += 1

        # 每 10 张写一次进度
        if session_count % CHECKPOINT_EVERY == 0:
            save_progress(prog)
            log.info(f"进度已保存（已处理 {session_count} 张）")

    # 最后写一次进度
    save_progress(prog)

    # ── 简报 ──────────────────────────────────────────────────────────────────
    log.info("=" * 60)
    log.info(f"本次处理张数     : {session_count}")
    log.info(f"保护期跳过       : {skip_protected}")
    log.info(f"已处理跳过       : {skip_already}")
    log.info(f"累计已处理（含本次）: {prog['total_processed']}")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
