"""
根目录整理迁移脚本。
用法:
  python scripts/organize.py --dry-run   # 仅打印迁移计划
  python scripts/organize.py             # 实际执行
"""
import argparse
from pathlib import Path
import shutil

BASE = Path(__file__).resolve().parent.parent

# ── 迁移规则 ──────────────────────────────────────────────────────────────────

RUNTIME_TO_DATA = [
    "progress.json",
    "suggested_tags.json",
    "pending.json",
    "pending_review.md",
    "vocab_feedback.md",
    "checkpoint_log.md",
    "review_queue.json",
    "review_batch_01.json",
    "ge_review_queue.json",
    "ge_need.json",
    "ge_skip.json",
    "ge_uncertain.json",
]

REPORTS_TO_REPORTS = [
    "REPORT.md",
    "RESUME.md",
    "REPORT_ge_triage.md",
    "REPORT_review.md",
]

DOCS_TO_ARCHIVE = [
    "Eagle打标项目-交接文档v1.3.md",
    "handoff.md",
    "handoff_20260501.md",
]

DOCS_TO_DOCS = [
    "PREFIXES.md",
    "SCAN_REPORT.md",
    "review_apply_log.md",
]

LOGS_TO_LOGS = [
    "review_warnings.log",
]

ROOT_TO_CONFIG = [
    "exceptions.json",
]


def collect_batch_results() -> list:
    return sorted(p.name for p in BASE.glob("batch_results_*.json") if p.is_file())


def plan_moves() -> list:
    moves = []
    for name in ROOT_TO_CONFIG:
        if (BASE / name).exists():
            moves.append((name, "config", str(BASE / "config" / name)))
    for name in RUNTIME_TO_DATA:
        if (BASE / name).exists():
            moves.append((name, "data", str(BASE / "data" / name)))
    for name in REPORTS_TO_REPORTS:
        if (BASE / name).exists():
            moves.append((name, "reports", str(BASE / "reports" / name)))
    for name in DOCS_TO_ARCHIVE:
        if (BASE / name).exists():
            moves.append((name, "archive", str(BASE / "archive" / name)))
    for name in DOCS_TO_DOCS:
        if (BASE / name).exists():
            moves.append((name, "docs", str(BASE / "docs" / name)))
    for name in LOGS_TO_LOGS:
        if (BASE / name).exists():
            moves.append((name, "logs", str(BASE / "logs" / name)))
    for name in collect_batch_results():
        moves.append((name, "data/batches", str(BASE / "data" / "batches" / name)))
    return moves


def ensure_dirs():
    for d in ["data", "data/batches", "docs", "reports", "archive", "logs", "config"]:
        (BASE / d).mkdir(parents=True, exist_ok=True)


def execute_moves(moves: list, dry_run: bool):
    if dry_run:
        print(f"{'=' * 60}")
        print(f" DRY-RUN 迁移计划（共 {len(moves)} 个文件）")
        print(f"{'=' * 60}\n")

        by_target = {}
        for name, dst_dir, _ in moves:
            by_target.setdefault(dst_dir, []).append(name)

        for dst_dir in ["config", "data", "data/batches", "reports", "archive", "docs", "logs"]:
            files = by_target.get(dst_dir, [])
            if not files:
                continue
            print(f"  -> {dst_dir}/ ({len(files)} 个)")
            for f in files:
                print(f"      {f}")
            print()

        print(f"{'=' * 60}")
        print(f" 确认无误后执行: python scripts/organize.py")
        print(f"{'=' * 60}")
        return

    ensure_dirs()
    moved = 0
    skipped = 0
    for name, dst_dir, dst_path in moves:
        src = BASE / name
        dst = Path(dst_path)
        if not src.exists():
            skipped += 1
            continue
        if dst.exists():
            print(f"  [skip] {name} -> {dst_dir}/ (already exists)")
            skipped += 1
            continue
        shutil.move(str(src), str(dst))
        print(f"  [done] {name} -> {dst_dir}/")
        moved += 1

    print(f"\n完成: {moved} moved, {skipped} skipped")


def main():
    parser = argparse.ArgumentParser(description="根目录整理迁移脚本")
    parser.add_argument("--dry-run", action="store_true", help="仅打印迁移计划")
    args = parser.parse_args()

    moves = plan_moves()
    if not moves:
        print("根目录已经干净，无需迁移。")
        return

    execute_moves(moves, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
