"""Local additions (not upstream): compact search, image preview, safe tag merge."""
import io
import os
from typing import Optional, List, Annotated
from urllib.parse import unquote

from mcp.types import TextContent
from pydantic import Field
from fastmcp import FastMCP
from fastmcp.utilities.types import Image
from utils.eagle_api import eagle_api_get, eagle_api_post

_library_path: Optional[str] = None


async def _get_library_path() -> Optional[str]:
    global _library_path
    if _library_path is None:
        lib = await eagle_api_get("/api/library/info")
        try:
            _library_path = lib["data"]["library"]["path"]
        except (KeyError, TypeError):
            return None
    return _library_path


def _compact(item: dict) -> dict:
    return {
        "id": item.get("id"),
        "name": item.get("name"),
        "ext": item.get("ext"),
        "tags": item.get("tags", []),
        "size": f'{item.get("width")}x{item.get("height")}',
        "annotation": (item.get("annotation") or "")[:120],
        "url": item.get("url") or "",
    }


def _load_preview(path: str, max_size: int) -> Optional[bytes]:
    from PIL import Image as PILImage

    try:
        with PILImage.open(path) as im:
            im.thumbnail((max_size, max_size))
            if im.mode not in ("RGB", "L"):
                bg = PILImage.new("RGB", im.size, (255, 255, 255))
                rgba = im.convert("RGBA")
                bg.paste(rgba, mask=rgba.split()[-1])
                im = bg
            buf = io.BytesIO()
            im.convert("RGB").save(buf, format="JPEG", quality=85)
            return buf.getvalue()
    except Exception:
        return None


def register_view_tools(mcp: FastMCP):
    @mcp.tool(tags={"Item"})
    async def find_items(
        tags: Annotated[
            Optional[str],
            Field(description="Comma-separated tags, e.g. '类-UI,派-包豪斯'"),
        ] = None,
        keyword: Annotated[
            Optional[str], Field(description="Keyword to match name/annotation")
        ] = None,
        ext: Annotated[Optional[str], Field(description="e.g. png, jpg, svg")] = None,
        limit: Annotated[int, Field(ge=1, le=200)] = 50,
        offset: Annotated[int, Field(ge=0)] = 0,
    ):
        """
        Search the Eagle library and return a compact list (id, name, ext, tags,
        size, annotation, url) instead of the full item records. Use this first,
        then view_items on a few ids to actually look at them.
        """
        params = {"limit": limit, "offset": offset}
        if tags:
            params["tags"] = tags
        if keyword:
            params["keyword"] = keyword
        if ext:
            params["ext"] = ext
        res = await eagle_api_get("/api/item/list", params)
        if not isinstance(res, dict) or res.get("status") != "success":
            return res
        items = [_compact(i) for i in res.get("data", []) if not i.get("isDeleted")]
        return {"status": "success", "count": len(items), "offset": offset, "items": items}

    @mcp.tool(tags={"Item"})
    async def view_items(
        item_ids: Annotated[
            List[str], Field(description="1-8 item IDs to look at", min_length=1, max_length=8)
        ],
        max_size: Annotated[
            int, Field(description="Longest side of each preview in px", ge=128, le=1568)
        ] = 640,
    ):
        """
        Return downscaled JPEG previews of Eagle items so the model can see them,
        plus a one-line text header per item (id, name, tags). Uses Eagle's
        thumbnail when present, otherwise the original file.
        """
        library_path = await _get_library_path()
        out: list = []
        for item_id in item_ids:
            info = await eagle_api_get("/api/item/info", {"id": item_id})
            if not isinstance(info, dict) or info.get("status") != "success":
                out.append(TextContent(type="text", text=f"[{item_id}] not found"))
                continue
            data = info["data"]
            name, ext = data.get("name", ""), data.get("ext", "")
            candidates: List[str] = []
            th = await eagle_api_get("/api/item/thumbnail", {"id": item_id})
            if isinstance(th, dict) and th.get("status") == "success" and th.get("data"):
                candidates += [th["data"], unquote(th["data"])]
            if library_path:
                base = os.path.join(library_path, "images", f"{item_id}.info")
                candidates += [
                    os.path.join(base, f"{name}_thumbnail.png"),
                    os.path.join(base, f"{name}.{ext}"),
                ]
            header = f"[{item_id}] {name}.{ext} | tags: {', '.join(data.get('tags', []))}"
            jpeg = None
            for c in candidates:
                if c and os.path.isfile(c):
                    jpeg = _load_preview(c, max_size)
                    if jpeg:
                        break
            out.append(TextContent(type="text", text=header if jpeg else header + " | (no previewable image)"))
            if jpeg:
                out.append(Image(data=jpeg, format="jpeg").to_image_content())
        return out

    @mcp.tool(tags={"Item"})
    async def add_item_tags(
        item_id: Annotated[str, Field(description="ID of the item")],
        tags: Annotated[List[str], Field(description="Tags to add (existing tags are kept)")],
    ):
        """
        Add tags to an item without removing its existing tags.
        Prefer this over update_item, which replaces the whole tag list.
        """
        info = await eagle_api_get("/api/item/info", {"id": item_id})
        if not isinstance(info, dict) or info.get("status") != "success":
            return {"status": "error", "message": f"item {item_id} not found"}
        current = info["data"].get("tags", [])
        merged = current + [t for t in tags if t not in current]
        if merged == current:
            return {"status": "success", "message": "no change", "tags": current}
        res = await eagle_api_post("/api/item/update", {"id": item_id, "tags": merged})
        if isinstance(res, dict) and res.get("status") == "success":
            return {"status": "success", "added": [t for t in merged if t not in current], "tags": merged}
        return res
