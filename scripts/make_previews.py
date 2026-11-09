"""agent 视觉模式配套：把 pending.json 里的素材生成统一尺寸预览图。

mimo API 停用后，视觉打标由 agent（Claude）直接读图完成。原图动辄几 MB /
几千像素，直接读会浪费大量 token，且 agent 侧本来就会降采样。这里统一压到
长边 640px 的 JPEG，文件名带 item_id，agent 看文件名即可对应回 Eagle 条目。

用法：
    python scripts/make_previews.py <输出目录> [--start N] [--count N]

输出：
    <输出目录>/000_<item_id>.jpg ...
    <输出目录>/manifest.json      # [{idx, item_id, name, ext, preview, existing_tags}]
"""
import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageOps

BASE_DIR = Path(__file__).resolve().parent.parent
PENDING_FILE = BASE_DIR / "data" / "pending.json"
MAX_EDGE = 640


def build(out_dir: Path, start: int, count: int) -> int:
    pending = json.loads(PENDING_FILE.read_text(encoding="utf-8"))
    subset = pending[start:start + count] if count > 0 else pending[start:]
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest = []
    failed = 0
    for offset, entry in enumerate(subset):
        idx = start + offset
        item_id = entry["item_id"]
        src = Path(entry["file_path"])
        dst = out_dir / f"{idx:03d}_{item_id}.jpg"
        if not src.exists():
            print(f"  [缺文件] {item_id} {src}")
            failed += 1
            continue
        try:
            with Image.open(src) as im:
                im = ImageOps.exif_transpose(im)
                # 带 alpha 的 PNG 直接 convert("RGB") 会丢掉透明通道，
                # 而这类素材（游戏 wiki 立绘等）RGB 常常全 0 → 整张变纯黑。
                # 先合成到白底再转，保证 agent 能看到内容。
                if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
                    im = im.convert("RGBA")
                    bg = Image.new("RGB", im.size, (255, 255, 255))
                    bg.paste(im, mask=im.split()[-1])
                    im = bg
                elif im.mode not in ("RGB", "L"):
                    im = im.convert("RGB")
                im.thumbnail((MAX_EDGE, MAX_EDGE), Image.LANCZOS)
                im.save(dst, "JPEG", quality=82)
        except Exception as exc:
            print(f"  [转换失败] {item_id}: {exc}")
            failed += 1
            continue

        manifest.append({
            "idx": idx,
            "item_id": item_id,
            "name": entry.get("name", ""),
            "ext": entry.get("ext", ""),
            "preview": str(dst),
            "existing_tags": entry.get("existing_tags", []),
        })

    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ 预览图 {len(manifest)} 张 → {out_dir}（失败 {failed}）")
    return failed


def main() -> int:
    ap = argparse.ArgumentParser(description="生成 agent 打标用的降采样预览图")
    ap.add_argument("out_dir", help="预览图输出目录")
    ap.add_argument("--start", type=int, default=0, help="从 pending 的第几条开始")
    ap.add_argument("--count", type=int, default=0, help="生成多少条，0 表示到结尾")
    args = ap.parse_args()
    build(Path(args.out_dir), args.start, args.count)
    return 0


if __name__ == "__main__":
    sys.exit(main())
