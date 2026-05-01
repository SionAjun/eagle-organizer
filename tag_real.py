"""
Eagle 素材库真实打标脚本
架构：
  --prepare --limit N        取待处理 items，输出路径列表 + 写 pending.json
  --apply --item ID --tags   单张模式：合并旧标签后写回 Eagle，落盘进度
  --apply-batch              批量模式：读 batch_results.json，批量写回 Eagle
  --checkpoint               手动触发检查点（更新所有状态文件 + REPORT.md）

批量流程（推荐）：
  1. python tag_real.py --prepare --limit 10
  2. 一次读取全部 10 张图，输出 JSON 写入 batch_results.json：
     [{"item_id": "xxx", "tags_to_add": ["类-角色设定", ...], "suggested": ["新概念"]}, ...]
  3. python tag_real.py --apply-batch
"""

import argparse
import base64
import json
import os
import re
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# ── 路径常量 ──────────────────────────────────────────────────────────────────
BASE_DIR            = Path(__file__).parent
CONFIG_DIR          = BASE_DIR / "config"
PROMPTS_DIR         = CONFIG_DIR / "prompts"
DERIVED_DIR         = BASE_DIR / "derived"
PROGRESS_FILE       = BASE_DIR / "progress.json"
PENDING_FILE        = BASE_DIR / "pending.json"
SUGGESTED_FILE      = BASE_DIR / "suggested_tags.json"
TAGS_FILE           = CONFIG_DIR / "tags.json"
BATCH_RESULTS_FILE  = BASE_DIR / "batch_results.json"
EXCEPTIONS_FILE     = CONFIG_DIR / "exceptions.json"
STATE_FILE          = DERIVED_DIR / "STATE.md"
RESUME_FILE         = BASE_DIR / "RESUME.md"
CHECKPOINT_LOG      = BASE_DIR / "checkpoint_log.md"
PENDING_REVIEW_FILE = BASE_DIR / "pending_review.md"
HANDOFF_FILE        = DERIVED_DIR / "HANDOFF.md"
REPORT_FILE         = BASE_DIR / "REPORT.md"

EAGLE_API        = "http://localhost:41595/api"
REPORTS_DIR      = BASE_DIR / "reports"

MIMO_API_KEY     = os.getenv("MIMO_API_KEY")
MIMO_BASE_URL    = os.getenv("MIMO_BASE_URL", "https://token-plan-cn.xiaomimimo.com/v1")
MIMO_MODEL       = os.getenv("MIMO_MODEL", "mimo-v2.5")
MIMO_TEMPERATURE = 0.3
MIMO_TOP_P       = 0.95

LIB_PATH         = Path("D:/杂项/素材.library")
PAGE_LIMIT       = 1000
PROTECTION_HOURS = 24
LIBRARY_TOTAL    = 20378
CHECKPOINT_EVERY      = 50
COMPRESS_AFTER        = 10   # 检查点超过此数时压缩旧记录
BATCH_SIZE            = 20
RECORDS_KEEP_RECENT   = 50
RECORDS_ARCHIVE_EVERY = 100
RECORDS_ARCHIVE_DIR   = BASE_DIR / "archive" / "records"
BATCHES_ARCHIVE_DIR   = BASE_DIR / "archive" / "batches"
BACKUPS_ARCHIVE_DIR   = BASE_DIR / "archive" / "backups"
REVIEW_ARCHIVE_DIR    = BASE_DIR / "archive" / "review"

# ── 回溯修复常量 ──────────────────────────────────────────────────────────────
DEPRECATED_TAGS = ["光-柔光", "材-金属", "材-皮革", "材-玻璃", "风-黑魂", "风-米哈游"]

REPLACEMENT_WHITELIST = {
    "光-柔光": [
        "光-白天", "光-黄昏", "光-黎明", "光-夜晚", "光-暗光",
        "光-顶光", "光-侧光", "光-底光", "光-伦勃朗光", "光-蝴蝶光",
        "光-边缘光", "光-轮廓光", "光-三点布光", "光-高反差",
        "光-丁达尔", "光-漫反射", "光-霓虹", "光-自发光",
    ],
    "材-金属": [
        "材-金属-光面", "材-金属-拉丝", "材-金属-生锈",
        "材-金属-烤漆", "材-金属-做旧", "材-金属-镀铬",
    ],
    "材-皮革": ["材-布料-皮革"],
    "材-玻璃": ["材-玻璃-清透", "材-玻璃-磨砂", "材-玻璃-彩色"],
    "风-黑魂": ["格-魂系"],
    "风-米哈游": ["格-绝区零"],  # 人工回溯后确认的唯一合法替换目标
}

REVIEW_QUEUE_FILE        = BASE_DIR / "review_queue.json"
GE_REVIEW_QUEUE_FILE     = BASE_DIR / "ge_review_queue.json"
GE_TRIAGE_NEED_FILE      = BASE_DIR / "ge_need.json"
GE_TRIAGE_SKIP_FILE      = BASE_DIR / "ge_skip.json"
GE_TRIAGE_UNCERTAIN_FILE = BASE_DIR / "ge_uncertain.json"
GE_TRIAGE_REPORT_FILE    = BASE_DIR / "REPORT_ge_triage.md"
REVIEW_WARNINGS_LOG     = BASE_DIR / "review_warnings.log"
REVIEW_REPORT_FILE      = BASE_DIR / "REPORT_review.md"
VOCAB_FEEDBACK_FILE     = BASE_DIR / "vocab_feedback.md"
REVIEW_CHECKPOINT_EVERY = 30

KNOWN_PREFIXES = ["类", "题", "风", "格", "版", "氛", "光", "镜", "构", "场", "角", "物", "材", "色", "教", "件", "载", "域", "派"]

# 排异规则：检测到某主类标签时，屏蔽不适用的前缀
# AI 打标时先判断主类，再用 get_filtered_tags() 拿到过滤后词表，根本看不到被屏蔽前缀的选项
INCOMPATIBLE_PREFIXES = {
    "类-UI":     ["镜", "光", "氛", "场", "构", "件", "载", "域"],
    "类-排版":   ["镜", "光", "氛", "场", "件", "载", "域"],
    "类-教程":   ["氛"],
    "类-拆解图": ["氛", "光"],
    "类-像素画": ["材"],  # 光前缀对像素画仍有意义，保留
}


def get_filtered_tags(primary_class_tag: str, tags_by_prefix: dict) -> dict:
    """返回排除不适用前缀后的词表（按前缀分组）。"""
    blocked = set(INCOMPATIBLE_PREFIXES.get(primary_class_tag, []))
    if not blocked:
        return tags_by_prefix
    return {pfx: lst for pfx, lst in tags_by_prefix.items() if pfx not in blocked}


def get_blocked_prefixes_from_tags(tags_to_add: list) -> list:
    """从已打标签中检测主类，返回应被屏蔽的前缀列表（供 apply 阶段校验用）。"""
    blocked = []
    for t in tags_to_add:
        if t in INCOMPATIBLE_PREFIXES:
            for pfx in INCOMPATIBLE_PREFIXES[t]:
                if pfx not in blocked:
                    blocked.append(pfx)
    return blocked

# ── Eagle API（绕过系统代理） ──────────────────────────────────────────────────
_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

def eagle_get(path: str) -> dict:
    with _opener.open(EAGLE_API + path, timeout=30) as r:
        return json.loads(r.read())

def eagle_post(path: str, body: dict) -> dict:
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req  = urllib.request.Request(
        EAGLE_API + path, data=data,
        headers={"Content-Type": "application/json"}, method="POST"
    )
    with _opener.open(req, timeout=30) as r:
        return json.loads(r.read())

# ── 工具函数 ──────────────────────────────────────────────────────────────────
def load_json(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default

def save_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

def load_prompt(name: str) -> str:
    """从 config/prompts/ 读取 prompt 模板文件。"""
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")

def _tag_name(t) -> str:
    """从标签对象或字符串提取标签名。"""
    return t["name"] if isinstance(t, dict) else t

def _update_tag_counts(tags_hit: list) -> None:
    """更新 tags.json 中的 hit_count / scope_count。每张图处理完后调用。"""
    tags_data = load_json(TAGS_FILE, {})
    tags_raw = tags_data.get("tags", {})
    hit_set = set(tags_hit)

    # 从命中标签反推主体类型
    subject_types = set()
    for t in tags_hit:
        if t.startswith("物-"):
            v = t.split("-", 1)[1]
            if v in ("载具", "摩托", "飞船"):
                subject_types.add("载具")
            elif v in ("机甲",):
                subject_types.add("机械")
            elif v in ("枪械", "近战武器", "战术装备"):
                subject_types.add("武器")
            elif v in ("电子设备", "零件", "柔性线缆", "主机箱"):
                subject_types.add("道具")
            elif v in ("服装", "配饰", "家具"):
                subject_types.add("装备")
            elif v in ("建筑",):
                subject_types.add("建筑")
        if t.startswith("角-"):
            subject_types.add("角色")

    for prefix, items in tags_raw.items():
        for item in items:
            if not isinstance(item, dict):
                continue
            name = item["name"]
            applies = item.get("applies_to", ["全图"])

            # hit_count
            if name in hit_set:
                item["hit_count"] = item.get("hit_count", 0) + 1

            # scope_count
            if "全图" in applies:
                item["scope_count"] = item.get("scope_count", 0) + 1
            elif subject_types & set(applies):
                item["scope_count"] = item.get("scope_count", 0) + 1

    save_json(TAGS_FILE, tags_data)

def load_tags() -> tuple:
    data     = load_json(TAGS_FILE, {})
    tags_raw = data.get("tags", {})
    all_tags = set()
    # 兼容 v2.3 对象格式和旧版字符串格式
    tags_by_pfx = {}
    for pfx, items in tags_raw.items():
        names = [_tag_name(t) for t in items]
        tags_by_pfx[pfx] = names
        all_tags.update(names)
    return tags_by_pfx, all_tags, data.get("version", "unknown")

def render_tag_catalog() -> str:
    """将 tags.json 渲染为人类可读的分组文本，注入 system prompt 末段。"""
    tags_data = load_json(TAGS_FILE, {})
    tags_by_pfx = tags_data.get("tags", {})
    # 兼容 v2.3 对象格式：提取 name 字段用于 prompt 渲染
    flat = {}
    for prefix, items in tags_by_pfx.items():
        flat[prefix] = [_tag_name(t) for t in items]
    total_tags = sum(len(v) for v in flat.values())
    prefix_count = len(flat)

    lines = [f"## 完整词表（共 {total_tags} 标签 / {prefix_count} 前缀，只允许从中选择）\n"]
    for prefix, tag_names in flat.items():
        lines.append(f"### {prefix}- （{len(tag_names)} 个）")
        lines.append("、".join(tag_names))
        lines.append("")

    lines.append("## 标签合法性硬约束")
    lines.append("- tags_to_add 数组中每一项**必须**逐字符匹配上面词表中的某个标签")
    lines.append("- 词表外的合理候选放入 suggested 字段（不要丢弃，也不要改写为相近词）")
    lines.append("- 不要使用 \"色-粉色\" \"构-仰视\" 这类词表外字面")
    return "\n".join(lines)

def fmt_modtime(ms: int) -> str:
    if not ms:
        return "[时间缺失]"
    return datetime.fromtimestamp(ms / 1000).strftime("%Y-%m-%d %H:%M")

def is_protected(item: dict) -> bool:
    btime_ms  = item.get("btime", 0)
    age_hours = (time.time() - btime_ms / 1000) / 3600
    return age_hours < PROTECTION_HOURS

def resolve_path(item: dict) -> Path:
    item_id = item["id"]
    name    = item.get("name", item_id)
    ext     = item.get("ext", "")
    return LIB_PATH / "images" / f"{item_id}.info" / f"{name}.{ext}"

def default_prog() -> dict:
    return {
        "processed_ids": [],
        "total_processed": 0,
        "tag_version_used": {},
        "last_run_time": None,
        "records": [],
        "round_start_time": None,
        "last_checkpoint_total": 0,
        "prepare_skip_stats": {"already_processed": 0, "protected_24h": 0, "time_missing_1970": 0},
        "apply_error_stats": {"api_error": 0, "read_fail": 0},
        "round_tag_input": 0,
        "round_tag_in_vocab": 0,
        "new_suggested_this_round": [],
        "archived_records_count": 0,
        "batch_counter": 0,
    }

def ensure_prog_fields(prog: dict) -> dict:
    for k, v in default_prog().items():
        if k not in prog:
            prog[k] = v
    return prog

# ── 分页拉取 ──────────────────────────────────────────────────────────────────
def iter_items():
    offset, empty_streak = 0, 0
    while True:
        try:
            data = eagle_get(f"/item/list?limit={PAGE_LIMIT}&offset={offset}").get("data", [])
        except Exception as e:
            print(f"  [警告] 分页请求异常 offset={offset}: {e}")
            empty_streak += 1
            if empty_streak >= 2:
                break
            offset += PAGE_LIMIT
            continue
        if not data:
            empty_streak += 1
            if empty_streak >= 2:
                break
        else:
            empty_streak = 0
            yield from data
        offset += PAGE_LIMIT

# ── mimo LLM 调用 ─────────────────────────────────────────────────────────────
_MIME_MAP = {
    "jpg":  "image/jpeg",
    "jpeg": "image/jpeg",
    "png":  "image/png",
    "webp": "image/webp",
    "gif":  "image/gif",
}

def build_messages(item: dict) -> list:
    """装配 mimo 视觉调用的 messages（system + user）。"""
    tags_data   = load_json(TAGS_FILE, {})
    tags_by_pfx = tags_data.get("tags", {})
    tags_ver    = tags_data.get("version", "unknown")
    all_tags    = [t for v in tags_by_pfx.values() for t in v]
    prefix_str  = "、".join(tags_by_pfx.keys())

    workflow         = load_json(CONFIG_DIR / "workflow.json", {})
    prog             = load_json(PROGRESS_FILE, default_prog())
    total            = prog.get("total_processed", 0)
    library_total    = workflow.get("library_total", LIBRARY_TOTAL)
    checkpoint_every = workflow.get("checkpoint_every_n", CHECKPOINT_EVERY)

    # system 块（静态内容，cache 友好）
    sys_text = (
        load_prompt("system.txt").format(
            tags_ver=tags_ver,
            tags_total=len(all_tags),
            prefix_count=len(tags_by_pfx),
            prefix_str=prefix_str,
        )
        + "\n\n" + load_prompt("排异.txt")
        + "\n\n" + load_prompt("格.txt")
        + "\n\n" + load_prompt("版.txt")
        + "\n\n" + load_prompt("自检.txt")
        + "\n\n" + load_prompt("反例.txt")
        + "\n\n" + load_prompt("域规则.txt")
        + "\n\n" + load_prompt("派规则.txt")
        + "\n\n" + render_tag_catalog()
    )

    # user 块（每张图变化）
    user_text = load_prompt("main.txt").format(
        total=total,
        library_total=library_total,
        checkpoint_every=checkpoint_every,
    )

    # 图片 base64
    img_path = resolve_path(item)
    ext      = item.get("ext", "jpg").lower()
    mime     = _MIME_MAP.get(ext, "image/jpeg")
    img_b64  = base64.b64encode(img_path.read_bytes()).decode("ascii")

    return [
        {"role": "system", "content": sys_text},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": user_text},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{img_b64}"}},
            ],
        },
    ]


def _extract_tags(raw: str) -> list:
    """从 LLM 响应中提取 tags_to_add（容错首尾杂字符）。"""
    try:
        return json.loads(raw).get("tags_to_add", [])
    except (json.JSONDecodeError, AttributeError):
        pass
    m = re.search(r'\{.+\}', raw, re.DOTALL)
    if not m:
        return []
    try:
        return json.loads(m.group()).get("tags_to_add", [])
    except (json.JSONDecodeError, AttributeError):
        return []


def call_mimo(messages: list, max_retries: int = 3):
    """调用 mimo API，返回 {raw, tags, usage}。429/5xx 指数退避。重试耗尽返回 None。"""
    time.sleep(0.75)  # 全局限速 ~80 RPM
    client   = OpenAI(api_key=MIMO_API_KEY, base_url=MIMO_BASE_URL)
    last_exc = None
    for attempt in range(max_retries):
        try:
            resp  = client.chat.completions.create(
                model=MIMO_MODEL,
                messages=messages,
                temperature=MIMO_TEMPERATURE,
                top_p=MIMO_TOP_P,
            )
            raw    = resp.choices[0].message.content or ""
            usage  = resp.usage
            details = getattr(usage, "prompt_tokens_details", None)
            cached  = getattr(details, "cached_tokens", 0) or 0
            return {
                "raw":  raw,
                "tags": _extract_tags(raw),
                "usage": {
                    "prompt_tokens":     usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "cached_tokens":     cached,
                },
            }
        except Exception as e:
            last_exc = e
            status   = getattr(e, "status_code", None)
            if status in (429,) or (status is not None and status >= 500):
                wait = 2 ** attempt
                print(f"  [mimo] HTTP {status} 退避 {wait}s (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait)
            else:
                # 非可重试异常(如 JSON parse)也纳入退避
                if attempt < max_retries - 1:
                    wait = 2 ** attempt
                    print(f"  [mimo] {type(e).__name__} 退避 {wait}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait)
                else:
                    break
    # 重试耗尽
    return None


# ── --prepare ─────────────────────────────────────────────────────────────────
def cmd_prepare(limit: int) -> None:
    prog          = ensure_prog_fields(load_json(PROGRESS_FILE, default_prog()))
    processed_set = set(prog.get("processed_ids", []))

    # 批次号管理（首次使用时从 total_processed 推算）
    if prog.get("batch_counter", 0) == 0 and prog.get("total_processed", 0) > 0:
        prog["batch_counter"] = prog["total_processed"] // BATCH_SIZE
        print(f"  [初始化] batch_counter 从 total_processed 推算为 {prog['batch_counter']}")
    prog["batch_counter"] = prog.get("batch_counter", 0) + 1
    batch_num_str = f"{prog['batch_counter']:03d}"

    # 每次 prepare 重置本轮统计
    prog["prepare_skip_stats"]      = {"already_processed": 0, "protected_24h": 0, "time_missing_1970": 0}
    prog["apply_error_stats"]       = {"api_error": 0, "read_fail": 0}
    prog["round_tag_input"]         = 0
    prog["round_tag_in_vocab"]      = 0
    prog["new_suggested_this_round"] = []
    prog["round_start_time"]        = datetime.now(timezone.utc).isoformat()

    pending        = []
    scanned        = 0
    skip_already   = 0
    skip_protected = 0
    skip_1970      = 0

    for item in iter_items():
        item_id = item["id"]
        if item_id in processed_set:
            skip_already += 1
            continue
        if is_protected(item):
            skip_protected += 1
            continue

        mod_ms = item.get("modificationTime", 0)
        if mod_ms < 1000:
            skip_1970 += 1

        scanned   += 1
        file_path  = resolve_path(item)

        try:
            info     = eagle_get(f"/item/info?id={item_id}")
            cur_tags = info.get("data", {}).get("tags", [])
        except Exception:
            cur_tags = item.get("tags", [])

        entry = {
            "index":            scanned,
            "item_id":          item_id,
            "name":             item.get("name", ""),
            "ext":              item.get("ext", ""),
            "file_path":        str(file_path),
            "existing_tags":    cur_tags,
            "modificationTime": mod_ms,
        }
        pending.append(entry)

        tags_display = cur_tags if cur_tags else "（无）"
        print(f"\n[{scanned}/{limit}] item_id: {item_id}")
        print(f"      文件名: {item.get('name', '')}.{item.get('ext', '')}")
        print(f"      路径: {file_path}")
        print(f"      已有标签: {tags_display}")
        print(f"      modificationTime: {fmt_modtime(mod_ms)}")

        if scanned >= limit:
            break

    prog["prepare_skip_stats"]["already_processed"] = skip_already
    prog["prepare_skip_stats"]["protected_24h"]     = skip_protected
    prog["prepare_skip_stats"]["time_missing_1970"] = skip_1970
    save_json(PROGRESS_FILE, prog)
    save_json(PENDING_FILE, pending)

    print(f"\n✅ pending.json 已保存（{len(pending)} 条）")
    print(f"   跳过已处理: {skip_already} | 24h保护: {skip_protected} | 1970时间: {skip_1970}")
    print(f"\n下一步（批量模式）：")
    print(f"  1. 一次读取全部 {len(pending)} 张图，输出 JSON 写入 batch_results_{batch_num_str}.json")
    print(f"  2. python tag_real.py --apply-batch")
    print(f"\n  📝 本批次编号: {batch_num_str}（断点恢复时按此编号命名结果文件）")

# ── 单张 apply 核心逻辑（批量和单张共用） ────────────────────────────────────
def _apply_one(item_id: str, tags_to_add: list, suggested_raw: list,
               prog: dict, sdata: dict,
               all_valid_tags: set, tag_version: str,
               pending_lookup: dict) -> bool:
    in_vocab     = [t for t in tags_to_add if t in all_valid_tags]
    out_of_vocab = [t for t in tags_to_add if t not in all_valid_tags]
    for t in suggested_raw:
        if t not in all_valid_tags and t not in out_of_vocab:
            out_of_vocab.append(t)

    prog["round_tag_input"]    = prog.get("round_tag_input", 0) + len(tags_to_add)
    prog["round_tag_in_vocab"] = prog.get("round_tag_in_vocab", 0) + len(in_vocab)

    # 排异规则校验：如果打了主类标签，检查是否有被屏蔽前缀下的标签混入
    blocked_pfx = get_blocked_prefixes_from_tags(tags_to_add)
    if blocked_pfx:
        violations = [t for t in in_vocab if any(t.startswith(p + "-") for p in blocked_pfx)]
        if violations:
            print(f"  [排异警告] 主类命中屏蔽规则，以下标签被过滤（不写入 Eagle）: {violations}")
            in_vocab = [t for t in in_vocab if t not in violations]

    if out_of_vocab:
        print(f"  [词表外，记录 suggested]: {out_of_vocab}")
        today          = datetime.now().strftime("%Y-%m-%d")
        smap           = sdata.setdefault("suggested", {})
        new_this_round = prog.setdefault("new_suggested_this_round", [])
        for t in out_of_vocab:
            if t in smap:
                smap[t]["count"] += 1
                ex = smap[t].setdefault("example_items", [])
                if item_id not in ex:
                    ex.append(item_id)
                    if len(ex) > 5:
                        smap[t]["example_items"] = ex[-5:]
                smap[t]["last_seen"] = today
            else:
                smap[t] = {"count": 1, "example_items": [item_id], "first_seen": today, "last_seen": today}
                if t not in new_this_round:
                    new_this_round.append(t)

    try:
        info     = eagle_get(f"/item/info?id={item_id}")
        old_tags = info.get("data", {}).get("tags", [])
    except Exception:
        old_tags = pending_lookup.get(item_id, {}).get("existing_tags", [])

    merged = list(old_tags)
    for t in in_vocab:
        if t not in merged:
            merged.append(t)

    try:
        resp = eagle_post("/item/update", {"id": item_id, "tags": merged})
        if resp.get("status") != "success":
            print(f"❌ Eagle API 写回失败 {item_id}: {resp}")
            prog["apply_error_stats"]["api_error"] = prog.get("apply_error_stats", {}).get("api_error", 0) + 1
            return False
    except Exception as e:
        print(f"❌ Eagle API 异常 {item_id}: {e}")
        prog["apply_error_stats"]["api_error"] = prog.get("apply_error_stats", {}).get("api_error", 0) + 1
        return False

    newly_added = [t for t in in_vocab if t not in old_tags]
    print(f"  ✅ {item_id} | 新增: {newly_added if newly_added else '（无新增）'} | 最终: {merged}")

    # 更新 tags.json 中的 hit_count / scope_count
    _update_tag_counts(in_vocab)

    if item_id not in prog["processed_ids"]:
        prog["processed_ids"].append(item_id)
        prog["total_processed"] = prog.get("total_processed", 0) + 1

    prog.setdefault("records", []).append({
        "item_id":      item_id,
        "tags_added":   newly_added,
        "tag_version":  tag_version,
        "processed_at": datetime.now(timezone.utc).isoformat(),
    })
    prog["tag_version_used"][item_id] = tag_version
    prog["last_run_time"]             = datetime.now(timezone.utc).isoformat()
    return True

# ── --apply（单张，保持兼容） ─────────────────────────────────────────────────
def cmd_apply(item_id: str, new_tags_raw: str) -> None:
    t0             = time.time()
    pending        = load_json(PENDING_FILE, [])
    pending_lookup = {e["item_id"]: e for e in pending}

    if item_id not in pending_lookup:
        print(f"❌ {item_id} 不在 pending.json 里，拒绝操作。")
        return

    _, all_valid_tags, tag_version = load_tags()
    raw_list = [t.strip() for t in new_tags_raw.split(",") if t.strip()]

    prog  = ensure_prog_fields(load_json(PROGRESS_FILE, default_prog()))
    sdata = load_json(SUGGESTED_FILE, {"version": "1.1", "suggested": {}})

    ok = _apply_one(item_id, raw_list, [], prog, sdata, all_valid_tags, tag_version, pending_lookup)

    save_json(SUGGESTED_FILE, sdata)
    save_json(PROGRESS_FILE, prog)

    elapsed = time.time() - t0
    if ok:
        print(f"   progress.json 已更新（累计 {prog['total_processed']} 张，单张耗时 {elapsed:.1f}s）")
        if prog["total_processed"] % CHECKPOINT_EVERY == 0:
            print(f"\n  [自动检查点] 已达 {prog['total_processed']} 张...")
            run_checkpoint(prog)
            save_json(PROGRESS_FILE, prog)

# ── --apply-batch ─────────────────────────────────────────────────────────────
def _classify_failure(e: Exception) -> str:
    status = getattr(e, "status_code", None)
    if status == 429:
        return "429"
    if status is not None and status >= 500:
        return "5xx"
    ename = type(e).__name__.lower()
    if "timeout" in ename:
        return "timeout"
    if "json" in ename:
        return "json_parse"
    return "unknown"


def cmd_apply_batch(batch_id: str = "", batch_size: int = 0) -> None:
    t0   = time.time()
    prog = ensure_prog_fields(load_json(PROGRESS_FILE, default_prog()))

    # 确定批次号
    if batch_id:
        batch_num = int(batch_id)
    else:
        batch_num = prog.get("batch_counter", 0)

    batch_file = BASE_DIR / f"batch_results_{batch_num:03d}.json"

    # 加载已有结果（断点恢复）
    if batch_file.exists():
        existing = load_json(batch_file, [])
        if isinstance(existing, list):
            batch_results = {r["item_id"]: r for r in existing if "item_id" in r}
        else:
            batch_results = existing
        print(f"  读取 {batch_file.name}（已有 {len(batch_results)} 条）")
    else:
        batch_results = {}

    # 加载 pending
    pending = load_json(PENDING_FILE, [])
    if not pending:
        print("❌ pending.json 为空，请先 --prepare")
        return

    # 限制本批张数
    limit = batch_size if batch_size > 0 else BATCH_SIZE
    pending = pending[:limit]
    total   = len(pending)

    _, all_valid_tags, tag_version = load_tags()
    sdata = load_json(SUGGESTED_FILE, {"version": "1.1", "suggested": {}})

    success_count = 0
    fail_count    = 0
    skip_count    = 0

    for i, entry in enumerate(pending, 1):
        item_id = entry["item_id"]

        # 断点恢复：跳过已处理
        prev = batch_results.get(item_id)
        if prev:
            if prev.get("status") == "success":
                print(f"[{i}/{total}] {item_id} 已成功，跳过")
                skip_count += 1
                continue
            if prev.get("status") == "failed":
                print(f"[{i}/{total}] {item_id} 已失败，跳过")
                skip_count += 1
                continue

        print(f"\n[{i}/{total}] {item_id}")

        # 获取 item 信息（含 id 字段供 resolve_path 使用）
        try:
            info = eagle_get(f"/item/info?id={item_id}")
            item = info.get("data") or info
            if not isinstance(item, dict) or "id" not in item:
                item = {**entry, "id": item_id}
        except Exception:
            item = {**entry, "id": item_id}

        # 调用 mimo
        result = call_mimo(build_messages(item))

        if result is None:
            # 重试耗尽，记录失败
            prev_attempt = 0
            if prev and prev.get("status") == "failed":
                prev_attempt = prev.get("failure_attempt", 0)
            batch_results[item_id] = {
                "item_id":           item_id,
                "status":            "failed",
                "failure_reason":    "mimo_exhausted",
                "failure_attempt":   prev_attempt + 1,
                "processed_at":      datetime.now(timezone.utc).isoformat(),
            }
            save_json(batch_file, list(batch_results.values()))
            fail_count += 1
            print(f"  ❌ mimo 失败（重试耗尽）")
            continue

        # 写回 Eagle
        tags_to_add = result["tags"]
        suggested   = []  # mimo 返回的 suggested 已在 _extract_tags 中丢弃
        ok = _apply_one(item_id, tags_to_add, suggested, prog, sdata, all_valid_tags, tag_version,
                        {e["item_id"]: e for e in pending})

        if ok:
            batch_results[item_id] = {
                "item_id":      item_id,
                "status":       "success",
                "tags_to_add":  tags_to_add,
                "raw_response": result["raw"],
                "usage":        result["usage"],
                "elapsed_ms":   int((time.time() - t0) * 1000 / i),
                "processed_at": datetime.now(timezone.utc).isoformat(),
            }
            success_count += 1
        else:
            batch_results[item_id] = {
                "item_id":         item_id,
                "status":          "failed",
                "failure_reason":  "eagle_write_error",
                "failure_attempt": 1,
                "processed_at":    datetime.now(timezone.utc).isoformat(),
            }
            fail_count += 1

        # 每张落盘
        save_json(batch_file, list(batch_results.values()))

        if ok and prog["total_processed"] % CHECKPOINT_EVERY == 0:
            print(f"\n  [自动检查点] 已达 {prog['total_processed']} 张...")
            save_json(SUGGESTED_FILE, sdata)
            run_checkpoint(prog)

    save_json(SUGGESTED_FILE, sdata)
    save_json(PROGRESS_FILE, prog)

    elapsed = time.time() - t0
    avg     = elapsed / total if total else 0
    print(f"\n✅ 批量完成：{success_count} 成功 / {fail_count} 失败 / {skip_count} 跳过（共 {total} 张）")
    print(f"   累计已处理: {prog['total_processed']} 张")
    print(f"   本批耗时: {elapsed:.1f}s（平均 {avg:.1f}s/张）")

    # 归档 pending
    BATCHES_ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    if PENDING_FILE.exists():
        try:
            dst = BATCHES_ARCHIVE_DIR / f"pending_{batch_num:03d}.json"
            PENDING_FILE.rename(dst)
            print(f"  [归档] pending.json → archive/batches/{dst.name}")
        except Exception as e:
            print(f"  [归档] pending.json 归档失败: {e}")

    _cleanup_dry_run_hint()
    cmd_sync()


# ── --retry-failed ────────────────────────────────────────────────────────────
def cmd_retry_failed(batch_id: str) -> None:
    batch_file = BASE_DIR / f"batch_results_{int(batch_id):03d}.json"
    if not batch_file.exists():
        print(f"❌ {batch_file.name} 不存在")
        return

    raw = load_json(batch_file, [])
    if isinstance(raw, list):
        batch_results = {r["item_id"]: r for r in raw if "item_id" in r}
    else:
        batch_results = raw

    failed_ids = [iid for iid, r in batch_results.items() if r.get("status") == "failed"]
    if not failed_ids:
        print("没有失败项需要重跑")
        return

    print(f"重跑 {len(failed_ids)} 个失败项...")

    prog = ensure_prog_fields(load_json(PROGRESS_FILE, default_prog()))
    _, all_valid_tags, tag_version = load_tags()
    sdata = load_json(SUGGESTED_FILE, {"version": "1.1", "suggested": {}})

    pending        = load_json(PENDING_FILE, [])
    pending_lookup = {e["item_id"]: e for e in pending}

    retried = 0
    for iid in failed_ids:
        prev = batch_results[iid]
        print(f"\n  重试 {iid}（上次原因: {prev.get('failure_reason', '?')}）")

        # 需要 item 信息来 build_messages
        if iid in pending_lookup:
            item = pending_lookup[iid]
        else:
            try:
                data = eagle_get(f"/item/info?id={iid}")
                item = data.get("data") or data
            except Exception as e:
                print(f"    ❌ 无法获取 item 信息: {e}")
                continue

        result = call_mimo(build_messages(item))

        if result is None:
            batch_results[iid] = {
                **prev,
                "failure_attempt": prev.get("failure_attempt", 0) + 1,
                "processed_at":    datetime.now(timezone.utc).isoformat(),
            }
            print(f"    ❌ 仍然失败")
        else:
            tags_to_add = result["tags"]
            ok = _apply_one(iid, tags_to_add, [], prog, sdata, all_valid_tags, tag_version, pending_lookup)
            if ok:
                batch_results[iid] = {
                    "item_id":      iid,
                    "status":       "success",
                    "tags_to_add":  tags_to_add,
                    "raw_response": result["raw"],
                    "usage":        result["usage"],
                    "processed_at": datetime.now(timezone.utc).isoformat(),
                }
                print(f"    ✅ 重试成功")
            else:
                batch_results[iid] = {
                    **prev,
                    "failure_attempt": prev.get("failure_attempt", 0) + 1,
                    "failure_reason":  "eagle_write_error",
                    "processed_at":    datetime.now(timezone.utc).isoformat(),
                }
                print(f"    ❌ Eagle 写回失败")

        retried += 1
        save_json(batch_file, list(batch_results.values()))

    save_json(SUGGESTED_FILE, sdata)
    save_json(PROGRESS_FILE, prog)
    print(f"\n✅ 重试完成：{retried} 张已处理")


# ── --batch-report ────────────────────────────────────────────────────────────
def cmd_batch_report(batch_id: str) -> None:
    batch_file = BASE_DIR / f"batch_results_{int(batch_id):03d}.json"
    if not batch_file.exists():
        print(f"❌ {batch_file.name} 不存在")
        return

    raw = load_json(batch_file, [])
    if isinstance(raw, list):
        results = raw
    else:
        results = list(raw.values())

    total   = len(results)
    success = [r for r in results if r.get("status") == "success"]
    failed  = [r for r in results if r.get("status") == "failed"]
    skipped = [r for r in results if r.get("status") not in ("success", "failed")]

    # token 统计
    usages = [r["usage"] for r in success if "usage" in r]
    avg_prompt     = sum(u["prompt_tokens"] for u in usages) / len(usages) if usages else 0
    avg_completion = sum(u["completion_tokens"] for u in usages) / len(usages) if usages else 0
    avg_cached     = sum(u["cached_tokens"] for u in usages) / len(usages) if usages else 0

    # 耗时
    elapsed_list = [r["elapsed_ms"] for r in success if "elapsed_ms" in r]
    avg_elapsed  = sum(elapsed_list) / len(elapsed_list) if elapsed_list else 0

    # 词表外
    _, all_valid_tags, _ = load_tags()
    oov_total = 0
    for r in success:
        for t in r.get("tags_to_add", []):
            if t not in all_valid_tags:
                oov_total += 1

    # raw_response 违规
    raw_violations = 0
    for r in success:
        raw = r.get("raw_response", "")
        if raw and not raw.strip().startswith("{"):
            raw_violations += 1

    # 失败列表
    fail_list = []
    for r in failed:
        fail_list.append({
            "item_id":          r.get("item_id", "?"),
            "failure_reason":   r.get("failure_reason", "?"),
            "failure_attempt":  r.get("failure_attempt", 1),
        })

    # 写报告
    REPORTS_DIR.mkdir(exist_ok=True)
    report_path = REPORTS_DIR / f"batch_{int(batch_id):03d}_report.md"

    lines = [
        f"# batch_{int(batch_id):03d} 报告",
        "",
        f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## 概览",
        "",
        f"| 指标 | 值 |",
        f"|------|-----|",
        f"| 总数 | {total} |",
        f"| 成功 | {len(success)} |",
        f"| 失败 | {len(failed)} |",
        f"| 跳过 | {len(skipped)} |",
        f"| 成功率 | {len(success)/total*100:.1f}% |" if total else "| 成功率 | N/A |",
        "",
        "## token / 耗时",
        "",
        f"| 指标 | 平均值 |",
        f"|------|--------|",
        f"| prompt_tokens | {avg_prompt:.0f} |",
        f"| completion_tokens | {avg_completion:.0f} |",
        f"| cached_tokens | {avg_cached:.0f} |",
        f"| 耗时 | {avg_elapsed:.0f} ms |",
        "",
        "## 质量",
        "",
        f"| 指标 | 值 |",
        f"|------|-----|",
        f"| 词表外标签数 | {oov_total} |",
        f"| raw_response 违规 | {raw_violations} |",
        "",
    ]

    if fail_list:
        lines.append("## 失败列表")
        lines.append("")
        lines.append("| item_id | 原因 | 重试次数 |")
        lines.append("|---------|------|---------|")
        for f in fail_list:
            lines.append(f"| {f['item_id']} | {f['failure_reason']} | {f['failure_attempt']} |")
        lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"✅ 报告已写入: reports/{report_path.name}")

    # 终端也输出关键数字
    print(f"\n  总数: {total} | 成功: {len(success)} | 失败: {len(failed)} | 跳过: {len(skipped)}")
    print(f"  成功率: {len(success)/total*100:.1f}%" if total else "  成功率: N/A")
    print(f"  平均 cached: {avg_cached:.0f} | 平均耗时: {avg_elapsed:.0f}ms")
    print(f"  词表外: {oov_total} | raw 违规: {raw_violations}")
    if fail_list:
        print(f"  失败项: {[f['item_id'] for f in fail_list]}")

# ── 自动化清理 ────────────────────────────────────────────────────────────────
# 活跃件白名单：永远不动这些文件
ACTIVE_ROOT_FILES = {
    "tag_real.py", "tags.json",
    "progress.json", "suggested_tags.json", "pending.json",
    "STATE.md", "RESUME.md", "HANDOFF.md", "REPORT.md",
    "CHANGELOG.md", "checkpoint_log.md",
    "pending_review.md", "vocab_feedback.md",
    "batch_results.json",
    "PREFIXES.md", "SCAN_REPORT.md",
    "Eagle打标项目-交接文档v1.md", "Eagle打标项目-交接文档v1.1.md",
}


def _current_tags_version() -> str:
    try:
        return load_json(TAGS_FILE, {}).get("version", "")
    except Exception:
        return ""


def _is_old_version_bak(path: Path, current_ver: str) -> bool:
    name = path.name
    if ".bak" not in name:
        return False
    if "tags.json.bak.v" in name:
        ver_part = name.split(".bak.v", 1)[-1]
        return ver_part != current_ver
    return True


def _archive_review_per_batch() -> list:
    archived = []
    queue_file = BASE_DIR / "review_queue.json"
    if not queue_file.exists():
        return archived
    queue = load_json(queue_file, [])
    if not queue:
        return archived
    queue_map = {e.get("item_id"): e for e in queue if isinstance(e, dict)}

    for batch_file in sorted(BASE_DIR.glob("review_batch_[0-9][0-9].json")):
        batch_data = load_json(batch_file, [])
        if not batch_data:
            continue
        batch_ids = [e.get("item_id") for e in batch_data if isinstance(e, dict)]
        all_done = all(
            queue_map.get(iid, {}).get("reviewed", False)
            for iid in batch_ids if iid
        )
        if not all_done:
            continue
        batch_num = batch_file.stem.rsplit("_", 1)[-1]
        results_file = BASE_DIR / f"review_batch_results_{batch_num}.json"
        REVIEW_ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        for src in [batch_file, results_file]:
            if src.exists():
                try:
                    src.rename(REVIEW_ARCHIVE_DIR / src.name)
                    archived.append(src.name)
                except Exception as e:
                    print(f"  [清理] {src.name} 归档失败: {e}")

    if queue_map and all(e.get("reviewed", False) for e in queue_map.values()):
        REVIEW_ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        for fname in ["review_queue.json", "review_decisions.json",
                      "review_apply_log.md", "REPORT_review.md"]:
            src = BASE_DIR / fname
            if src.exists():
                try:
                    src.rename(REVIEW_ARCHIVE_DIR / src.name)
                    archived.append(src.name)
                except Exception as e:
                    print(f"  [清理] {src.name} 归档失败: {e}")
    return archived


def _archive_old_baks(current_ver: str, dry_run: bool = False) -> list:
    actions = []
    for path in BASE_DIR.glob("*.bak*"):
        if not path.is_file():
            continue
        if path.name in ACTIVE_ROOT_FILES:
            continue
        if _is_old_version_bak(path, current_ver):
            target = BACKUPS_ARCHIVE_DIR / path.name
            if dry_run:
                actions.append(f"[计划] {path.name} → archive/backups/")
            else:
                BACKUPS_ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
                try:
                    path.rename(target)
                    actions.append(f"[已动] {path.name} → archive/backups/")
                except Exception as e:
                    actions.append(f"[失败] {path.name}: {e}")
    return actions


def auto_cleanup_safe() -> None:
    try:
        archived = _archive_review_per_batch()
        if archived:
            print(f"  [自动清理] 已归档 {len(archived)} 个 review_* 文件:")
            for n in archived:
                print(f"             - {n}")
    except Exception as e:
        print(f"  [自动清理] 出错(已忽略,不影响主流程): {e}")


def _cleanup_dry_run_hint() -> None:
    try:
        cur_ver = _current_tags_version()
        plans = _archive_old_baks(cur_ver, dry_run=True)
        if plans:
            print(f"\n  💡 检测到 {len(plans)} 个可清理 .bak 文件:")
            for p in plans[:5]:
                print(f"     {p}")
            if len(plans) > 5:
                print(f"     ... 还有 {len(plans) - 5} 个")
            print(f"     执行 `python tag_real.py --cleanup` 处理(--dry-run 预览)")
    except Exception:
        pass


def cmd_cleanup(dry_run: bool = False) -> None:
    print(f"\n{'━'*50}")
    print(f" 自动化清理 {'[DRY-RUN 预览模式]' if dry_run else '[实际执行]'}")
    print(f"{'━'*50}")

    cur_ver = _current_tags_version()
    print(f" 当前 tags.json 版本: {cur_ver or '(读取失败)'}")
    print(f" 活跃件白名单数量: {len(ACTIVE_ROOT_FILES)}")

    print(f"\n [规则 ①C] 旧版本 .bak 文件:")
    bak_actions = _archive_old_baks(cur_ver, dry_run=dry_run)
    if bak_actions:
        for a in bak_actions:
            print(f"   {a}")
    else:
        print(f"   (无可归档 .bak 文件)")

    print(f"\n [规则 ②B] 批次完成的 review_* 文件:")
    if dry_run:
        queue_file = BASE_DIR / "review_queue.json"
        if queue_file.exists():
            queue = load_json(queue_file, [])
            done = sum(1 for e in queue if isinstance(e, dict) and e.get("reviewed", False))
            total = len(queue)
            print(f"   review_queue.json: {done}/{total} 完成")
            if done == total and total > 0:
                print(f"   [计划] 全队列完成,可归档 review_queue.json + review_decisions.json + 等")
            else:
                print(f"   (队列未全完成)")
        else:
            print(f"   (无 review_queue.json)")
    else:
        review_archived = _archive_review_per_batch()
        if review_archived:
            for n in review_archived:
                print(f"   [已动] {n} → archive/review/")
        else:
            print(f"   (无可归档 review_* 文件)")

    print(f"\n [诊断] 根目录非白名单文件:")
    extras = []
    for path in BASE_DIR.iterdir():
        if not path.is_file():
            continue
        name = path.name
        if name in ACTIVE_ROOT_FILES:
            continue
        if name.startswith("batch_results_") and name.endswith(".json"):
            continue
        if name.startswith("pending_") and name.endswith(".json"):
            continue
        if ".bak" in name:
            continue
        if name.startswith("review_"):
            continue
        extras.append(name)
    if extras:
        for n in extras:
            print(f"   ⚠️  {n}  (未识别,人工确认)")
    else:
        print(f"   ✅ 根目录干净")

    print(f"\n{'━'*50}\n")


# ── records 归档 ──────────────────────────────────────────────────────────────
def archive_old_records(prog: dict) -> None:
    records   = prog.get("records", [])
    threshold = RECORDS_KEEP_RECENT + RECORDS_ARCHIVE_EVERY
    if len(records) <= threshold:
        return
    RECORDS_ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    to_archive    = records[:RECORDS_ARCHIVE_EVERY]
    archived_done = prog.get("archived_records_count", 0)
    start_n       = archived_done + 1
    end_n         = archived_done + len(to_archive)
    archive_path  = RECORDS_ARCHIVE_DIR / f"records_{start_n:04d}-{end_n:04d}.json"
    save_json(archive_path, to_archive)
    prog["records"]                = records[RECORDS_ARCHIVE_EVERY:]
    prog["archived_records_count"] = end_n
    print(f"  [归档] 已归档 {len(to_archive)} 条（第 {start_n}-{end_n} 张）→ {archive_path.name}，主文件保留 {len(prog['records'])} 条")


# ── REPORT.md ─────────────────────────────────────────────────────────────────
def write_report(prog: dict) -> None:
    now     = datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M")

    total   = prog.get("total_processed", 0)
    last_cp = prog.get("last_checkpoint_total", 0)
    round_z = total - last_cp
    start_x = last_cp + 1
    end_y   = total

    # 耗时计算
    round_start_iso = prog.get("round_start_time")
    if round_start_iso and round_z > 0:
        try:
            start_dt    = datetime.fromisoformat(round_start_iso.replace("Z", "+00:00"))
            elapsed_sec = (now.astimezone(timezone.utc) - start_dt).total_seconds()
            elapsed_min = round(elapsed_sec / 60, 1)
            avg_sec_per = round(elapsed_sec / round_z, 1)
        except Exception:
            elapsed_min = "估算"
            avg_sec_per = "估算"
    else:
        elapsed_min = "估算"
        avg_sec_per = "估算"

    # 本轮 records（归档安全：用末尾 N 条而非绝对索引）
    records       = prog.get("records", [])
    round_count   = total - last_cp
    round_records = records[-round_count:] if round_count > 0 and records else []

    # TOP10 标签
    tag_counter: dict = {}
    for r in round_records:
        for t in r.get("tags_added", []):
            tag_counter[t] = tag_counter.get(t, 0) + 1
    top10 = sorted(tag_counter.items(), key=lambda x: -x[1])[:10]
    top10_str = ", ".join(f"{t}: {c}" for t, c in top10) if top10 else "（无）"

    # 未使用前缀
    used_pfx = set()
    for t in tag_counter:
        for pfx in KNOWN_PREFIXES:
            if t.startswith(pfx + "-"):
                used_pfx.add(pfx)
                break
    unused_pfx = [p for p in KNOWN_PREFIXES if p not in used_pfx]
    unused_str = str(unused_pfx) if unused_pfx else "（全部前缀均有使用）"

    # suggested 统计
    sdata      = load_json(SUGGESTED_FILE, {"version": "1.1", "suggested": {}})
    smap       = sdata.get("suggested", {})
    sug_total  = len(smap)
    sug_review = sum(1 for v in smap.values() if v.get("count", 0) >= 3)
    new_sug    = prog.get("new_suggested_this_round", [])

    # 跳过 / 报错统计
    skip = prog.get("prepare_skip_stats", {})
    err  = prog.get("apply_error_stats", {})

    # 效率指标
    avg_tags = (
        round(sum(len(r.get("tags_added", [])) for r in round_records) / round_z, 1)
        if round_z > 0 else "N/A"
    )
    tag_in   = prog.get("round_tag_input", 0)
    tag_voc  = prog.get("round_tag_in_vocab", 0)
    hit_rate = f"{tag_voc / tag_in * 100:.1f}%" if tag_in > 0 else "N/A"

    tags_ver = load_json(TAGS_FILE, {}).get("version", "1.0")

    report = f"""# Eagle 打标项目运行报告
生成时间: {now_str}
报告区间: 第{start_x}张 → 第{end_y}张（本轮处理 {round_z} 张）

## 进度
- 总量: {LIBRARY_TOTAL}
- 已处理: {total}
- 完成率: {total / LIBRARY_TOTAL * 100:.2f}%
- 本轮耗时: {elapsed_min}分钟（从启动到本检查点）
- 平均每张耗时: {avg_sec_per}秒

## 标签统计
- tags.json 版本: {tags_ver}
- 本轮使用频率 TOP10 标签: {top10_str}
- 本轮从未使用的前缀: {unused_str}
- suggested 总条目数: {sug_total}
- 其中 count>=3 待审核: {sug_review} 条
- 新增 suggested: {new_sug if new_sug else "（无）"}

## 异常与跳过
- 跳过已处理: {skip.get("already_processed", 0)} 张
- 跳过24h保护期: {skip.get("protected_24h", 0)} 张
- 时间缺失(1970): {skip.get("time_missing_1970", 0)} 张
- API 报错: {err.get("api_error", 0)} 次
- 读图失败: {err.get("read_fail", 0)} 次（由外部 Claude 报告，此处为估算）

## 效率指标
- 每张平均打标数: {avg_tags} 个
- 词表命中率: {hit_rate}（词表内标签数 / 总输入标签数）
- 批次大小: 每次处理 {BATCH_SIZE} 张（批量模式）

## 待决策事项
- {"需要审核 " + str(sug_review) + " 个 count>=3 的 suggested 标签（见 pending_review.md）" if sug_review > 0 else "无待审核项"}

## Claude Code 自评
- 最浪费 token 的环节：单张模式下每张图需独立一次上下文 + 一次工具调用往返；批量 {BATCH_SIZE} 张后上下文共享，前置 tags.json 词表只读一次，预计节省约 {BATCH_SIZE - 1}x 前置文本 token。
- 改进建议：如批量质量下降或超时，请将 BATCH_SIZE 从 10 降至 5，并在下一份报告的自评里说明。
"""
    REPORT_FILE.write_text(report, encoding="utf-8")
    print(f" REPORT.md:     ✅ 已覆盖写入")

# ── 检查点压缩 ────────────────────────────────────────────────────────────────
def compress_checkpoints() -> None:
    """checkpoint_log.md / HANDOFF.md 超过 compress_after 条时压缩旧记录。"""
    cfg = load_json(CONFIG_DIR / "workflow.json", {})
    threshold = cfg.get("compress_after", COMPRESS_AFTER)
    # ── checkpoint_log.md 压缩 ──────────────────────────────────────────────
    if CHECKPOINT_LOG.exists():
        lines = CHECKPOINT_LOG.read_text(encoding="utf-8").splitlines()
        # 只压缩非空、非已压缩的行
        real_lines = [l for l in lines if l.strip() and not l.startswith("<!--compressed")]
        if len(real_lines) > threshold:
            old_lines = real_lines[:-threshold]
            keep_lines = real_lines[-threshold:]
            # 从旧行提取关键信息
            first_ts = old_lines[0].split("]")[0].lstrip("[") if "]" in old_lines[0] else "?"
            last_ts  = old_lines[-1].split("]")[0].lstrip("[") if "]" in old_lines[-1] else "?"
            # 提取已处理数量
            import re
            nums = []
            for l in old_lines:
                m = re.search(r"已处理 (\d+)/", l)
                if m:
                    nums.append(int(m.group(1)))
            proc_range = f"{min(nums)}→{max(nums)}" if nums else "?"
            summary = (
                f"<!--compressed--> [{first_ts} ~ {last_ts}] "
                f"检查点 #1~#{len(old_lines)} | "
                f"已处理 {proc_range}/{LIBRARY_TOTAL} | "
                f"（已压缩，详见 archive/）\n"
            )
            # 备份旧记录到 archive
            archive_dir = BASE_DIR / "archive"
            archive_dir.mkdir(exist_ok=True)
            backup_path = archive_dir / f"checkpoint_log_archive_{datetime.now():%Y%m%d_%H%M}.md"
            backup_path.write_text("\n".join(old_lines) + "\n", encoding="utf-8")
            # 写入压缩后的文件
            CHECKPOINT_LOG.write_text(summary + "\n".join(keep_lines) + "\n", encoding="utf-8")
            print(f" checkpoint_log:  🗜️ 压缩 {len(old_lines)} 条 → 摘要 + 最近 {threshold} 条")

    # ── HANDOFF.md 压缩 ─────────────────────────────────────────────────────
    if HANDOFF_FILE.exists():
        content = HANDOFF_FILE.read_text(encoding="utf-8")
        # 按 ## 检查点 分割
        import re
        sections = re.split(r"(?=^## 检查点 )", content, flags=re.MULTILINE)
        # 第一段可能是空或非检查点内容
        header = ""
        cp_sections = []
        for s in sections:
            if s.startswith("## 检查点 "):
                cp_sections.append(s)
            else:
                header += s
        if len(cp_sections) > threshold:
            old_secs = cp_sections[:-threshold]
            keep_secs = cp_sections[-threshold:]
            # 提取关键信息
            first_line = old_secs[0].split("\n")[0]
            last_line = old_secs[-1].split("\n")[0]
            import re as re2
            nums = []
            for s in old_secs:
                m = re2.search(r"已处理: (\d+)/", s)
                if m:
                    nums.append(int(m.group(1)))
            proc_range = f"{min(nums)}→{max(nums)}" if nums else "?"
            summary_sec = (
                f"## 检查点压缩摘要（{len(old_secs)} 条）\n"
                f"- 时间跨度: {first_line.split('|')[0].strip().replace('## 检查点 ','')} ~ {last_line.split('|')[0].strip().replace('## 检查点 ','')}\n"
                f"- 已处理: {proc_range}/{LIBRARY_TOTAL}\n"
                f"- 详细记录已归档至 archive/\n\n"
            )
            # 备份
            archive_dir = BASE_DIR / "archive"
            archive_dir.mkdir(exist_ok=True)
            backup_path = archive_dir / f"handoff_archive_{datetime.now():%Y%m%d_%H%M}.md"
            backup_path.write_text("".join(old_secs), encoding="utf-8")
            HANDOFF_FILE.write_text(header + summary_sec + "".join(keep_secs), encoding="utf-8")
            print(f" HANDOFF.md:      🗜️ 压缩 {len(old_secs)} 条 → 摘要 + 最近 {threshold} 条")

# ── 检查点 ────────────────────────────────────────────────────────────────────
def run_checkpoint(prog: dict, force: bool = False) -> None:
    total        = prog.get("total_processed", 0)
    checkpoint_n = max(total // CHECKPOINT_EVERY, 1) if force else (total // CHECKPOINT_EVERY)
    tags_ver     = load_json(TAGS_FILE, {}).get("version", "unknown")

    records   = prog.get("records", [])
    last      = records[-1] if records else {}
    last_id   = last.get("item_id", "—")
    last_name = "—"
    pending   = load_json(PENDING_FILE, [])
    match     = next((e for e in pending if e["item_id"] == last_id), None)
    if match:
        last_name = f"{match['name']}.{match['ext']}"

    tags_data           = load_json(TAGS_FILE, {})
    tags_total          = sum(len(v) for v in tags_data.get("tags", {}).values())
    tags_prefixes       = list(tags_data.get("tags", {}).keys())
    prefix_count        = len(tags_prefixes)
    prefix_str          = "、".join(tags_prefixes)
    sdata_cp            = load_json(SUGGESTED_FILE, {"version": "1.1", "suggested": {}})
    smap_cp             = sdata_cp.get("suggested", {})
    suggested_keys      = list(smap_cp.keys())
    pending_review_tags = [k for k, v in smap_cp.items() if v.get("count", 0) >= 3]
    now_str             = datetime.now().strftime("%Y-%m-%d %H:%M")

    # ── REPORT.md（先写，使用 last_checkpoint_total 的旧值计算区间） ──────────
    write_report(prog)

    # 更新 last_checkpoint_total（write_report 之后再更新，区间才正确）
    prog["last_checkpoint_total"] = total

    # ── STATE.md ──────────────────────────────────────────────────────────────
    # 从 config/prompts/ 加载 prompt 模板并格式化
    _sys  = load_prompt("system.txt").format(
        tags_ver=tags_ver, tags_total=tags_total,
        prefix_count=prefix_count, prefix_str=prefix_str,
    )
    _main = load_prompt("main.txt").format(
        checkpoint_every=CHECKPOINT_EVERY, total=total, library_total=LIBRARY_TOTAL,
    )
    _ge   = load_prompt("格.txt")
    _paiyi = load_prompt("排异.txt")
    _zijian = load_prompt("自检.txt")
    _prompt_section = (
        f"## 给下次会话 Claude Code 的指令（Eagle 素材打标 v{tags_ver}，{now_str}）\n\n"
        f"{_sys}\n\n"
        f"{_main}\n\n"
        f"{_paiyi}\n\n"
        f"{_ge}\n\n"
        f"{_zijian}\n"
    )
    state_content = f"""# Eagle 素材库打标签项目 — 当前状态

最后更新：{now_str}　　进度：{total} / {LIBRARY_TOTAL} 张

---

## 当前进度

- **已处理**：{total} / {LIBRARY_TOTAL} 张（{total/LIBRARY_TOTAL*100:.2f}%）
- **最后处理**：`{last_id}`　`{last_name}`
- **待审建议标签**：{suggested_keys if suggested_keys else "（无）"}

---

## 已完成事项

- Eagle API 连通性验证（`http://localhost:41595/api`，Eagle 4.0 Build 20250627）
- 资源库：素材，路径 `D:\\杂项\\素材.library`，共 {LIBRARY_TOTAL} 张 / 121 个文件夹
- dry_run.py 骨架验证通过（分页、排序、断点续跑全部正常）
- tags.json 词表生成完毕（version {tags_ver}，{tags_total} 个标签，{prefix_count} 个前缀）
- tag_real.py 真实打标脚本验证通过，链路完整（取图→看图→打标→写回→落盘）
- 检查点机制已建立（每 50 张自动触发，含 REPORT.md 覆盖写入）
- 批量读图模式（每批 {BATCH_SIZE} 张，tags.json 一次加载）

---

## 踩过的坑与解决方案

| 坑 | 现象 | 解决方案 |
|---|---|---|
| 系统代理劫持 localhost | curl/urllib 走 127.0.0.1:7892，返回 502 | `urllib.request.ProxyHandler({{}})` 绕过 |
| limit 小时分页静默截断 | `limit=50` 只能访问约 440 条 | 统一用 `limit=1000` |
| Eagle API 无总数字段 | `/api/item/list` 无 total | `limit=25000` 探底得 20378 |
| orderBy=-CREATEDATE 排序反了 | 加参数后返回 1970 epoch 老素材 | 去掉 orderBy，依赖 Eagle 默认倒序 |
| btime 字段大量为 0 | 老素材 btime=Unix 纪元 | 改用 `modificationTime` 字段 |
| `/api/v2/` 端点不存在 | Eagle 4.0 没有 v2 API | 全部使用 `/api/` 前缀 |
| limit=200 offset=200 返回空 | Eagle API limit 影响可访问总量 | 用大 limit（1000）单次拉取 |

---

## 下一步待办

1. 执行 `python tag_real.py --prepare --limit {BATCH_SIZE}`
2. 一次读取全部 {BATCH_SIZE} 张图，输出 JSON 写入 batch_results.json
3. 执行 `python tag_real.py --apply-batch`
4. 每 50 张自动触发检查点（含 REPORT.md 生成）
5. 累积建议标签后，与用户确认是否加入词表并更新 version

---

## 关键约束（不可违反）

- 标签严格从 `tags.json` 词表选，**绝不自由发挥**
- 词表版本 {tags_ver}，共 {tags_total} 个标签，{prefix_count} 个前缀：{prefix_str}
- 每张图只做一次视觉分析
- 新素材保护期：btime < 24 小时的跳过
- 分页：`limit=1000`，不传 `orderBy`
- 写回前先拉旧标签合并，不覆盖用户手动标签
- 词表外概念写 `suggested_tags.json`，不擅自加到素材
- 批量模式：一次 {BATCH_SIZE} 张，tags.json 只加载一次

---

{_prompt_section}
"""

    # ── RESUME.md ─────────────────────────────────────────────────────────────
    resume_content = f"""# 下次启动指引

**第一件事：读 STATE.md，了解当前进度和所有已踩的坑。**

---

## 当前进度（{now_str} 更新）

已处理 **{total} / {LIBRARY_TOTAL}** 张（{total/LIBRARY_TOTAL*100:.2f}%）

---

## 启动顺序

1. 读 `STATE.md`（全部上下文、踩坑记录）
2. 读 `tags.json`（词表，{tags_total} 个标签，version {tags_ver}）
3. 读 `progress.json`（已处理 ID 列表，跳过这些）
4. 读 `suggested_tags.json`（待审建议标签，先展示给用户）

---

## 下一步操作（批量模式）

```bash
python tag_real.py --prepare --limit {BATCH_SIZE}
```

一次读取全部 {BATCH_SIZE} 张图，输出如下 JSON 写入 batch_results.json：

```json
[
  {{"item_id": "xxx", "tags_to_add": ["类-角色设定", "风-写实"], "suggested": ["新概念"]}},
  ...
]
```

```bash
python tag_real.py --apply-batch
```

---

## 不需要重做的事

- API 连通性测试（已验证）
- 项目结构（所有文件已存在）
- dry_run.py 验证（已通过）
- 分页/排序/代理的任何诊断（结论在 STATE.md）
- progress.json 里已有 {total} 条记录，--apply-batch 会自动跳过已处理项

---

## 关键记住

- 系统代理劫持 localhost，脚本已用 `ProxyHandler({{}})` 绕过
- 分页用 `limit=1000`，不传 `orderBy`
- 写回前自动拉旧标签合并，不覆盖手动标签
- 每 50 张自动检查点；也可手动：`python tag_real.py --checkpoint`
- tags.json 在一个批次内只加载一次（_apply_one 复用已加载的 all_valid_tags）
"""
    RESUME_FILE.write_text(resume_content, encoding="utf-8")

    # ── pending_review.md（count≥3 条目） ────────────────────────────────────
    if pending_review_tags:
        review_lines = [f"# 待审标签（count≥3）\n\n生成时间：{now_str}\n\n---\n"]
        for tag in pending_review_tags:
            entry = smap_cp[tag]
            review_lines.append(f"\n## `{tag}`\n\n")
            review_lines.append(f"- **count**: {entry['count']}\n")
            review_lines.append(f"- **example_items**: {entry.get('example_items', [])}\n")
            review_lines.append(f"- **first_seen**: {entry.get('first_seen', '?')}\n")
            review_lines.append(f"- **last_seen**: {entry.get('last_seen', '?')}\n")
            review_lines.append(f"- **决定**: （填 yes 加入词表 / 填 no 忽略）\n")
        PENDING_REVIEW_FILE.write_text("".join(review_lines), encoding="utf-8")

    # ── checkpoint_log.md 追加 ────────────────────────────────────────────────
    log_line = (
        f"[{now_str}] 检查点 #{checkpoint_n} | "
        f"已处理 {total}/{LIBRARY_TOTAL} | "
        f"建议词表 {len(smap_cp)} 个: {suggested_keys} | "
        f"待审 count≥3: {len(pending_review_tags)} 个\n"
    )
    with open(CHECKPOINT_LOG, "a", encoding="utf-8") as f:
        f.write(log_line)

    # ── records 归档（write_report 之后，save 之前） ──────────────────────────
    archive_old_records(prog)

    # ── 自动化清理钩子(review_* 按批次完成归档) ──────────────────────────
    auto_cleanup_safe()

    # ── 终端报告 ──────────────────────────────────────────────────────────────
    print(f"\n{'━'*50}")
    print(f" 检查点 #{checkpoint_n}")
    print(f"{'━'*50}")
    print(f" 已处理:           {total} / {LIBRARY_TOTAL} ({total/LIBRARY_TOTAL*100:.2f}%)")
    print(f" 最后处理:         {last_id}  {last_name}")
    print(f" 建议词表:         {suggested_keys if suggested_keys else '（无）'}")
    print(f" 待审 count≥3:     {len(pending_review_tags)} 条{'  → pending_review.md 已更新' if pending_review_tags else ''}")
    print(f" RESUME.md:       ✅ 已更新")
    print(f" checkpoint_log:  ✅ 已追加")
    print(f" REPORT.md:       ✅ 已覆盖写入")
    print(f"{'━'*50}\n")
    compress_checkpoints()
    cmd_sync()


# ── 回溯修复：工具函数 ────────────────────────────────────────────────────────
def log_review_warning(item_id: str, message: str) -> None:
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line    = f"[{now_str}] {item_id}: {message}\n"
    with open(REVIEW_WARNINGS_LOG, "a", encoding="utf-8") as f:
        f.write(line)
    print(f"  ⚠️  [警告记录] {message}")


def get_review_batch_path(batch_num: str, results: bool = False) -> Path:
    prefix = "review_batch_results" if results else "review_batch"
    return BASE_DIR / f"{prefix}_{batch_num}.json"


def get_next_batch_num() -> str:
    existing = sorted(BASE_DIR.glob("review_batch_[0-9][0-9].json"))
    if not existing:
        return "01"
    last_n = int(existing[-1].stem.rsplit("_", 1)[-1])
    return f"{last_n + 1:02d}"


# ── --build-review-queue ──────────────────────────────────────────────────────
def cmd_build_review_queue() -> None:
    prog    = load_json(PROGRESS_FILE, default_prog())
    records = prog.get("records", [])

    queue  = []
    counts = {dep: 0 for dep in DEPRECATED_TAGS}

    for rec in records:
        tags_added = rec.get("tags_added", [])
        # 精确列表成员匹配，不做字符串包含
        found = [dep for dep in DEPRECATED_TAGS if dep in tags_added]
        if found:
            for dep in found:
                counts[dep] += 1
            queue.append({
                "item_id":         rec["item_id"],
                "deprecated_found": found,
                "tags_at_tagging": tags_added,
                "reviewed":        False,
                "reviewed_at":     None,
            })

    save_json(REVIEW_QUEUE_FILE, queue)

    expected = {"光-柔光": 64, "材-金属": 33, "材-皮革": 2, "材-玻璃": 2, "风-黑魂": 0, "风-米哈游": 7}
    expected_total = sum(expected.values())
    print(f"\n✅ --build-review-queue 完成")
    print(f"   检测到废弃标签条目: {len(queue)} 条")
    for dep in DEPRECATED_TAGS:
        exp = expected.get(dep, "?")
        mark = "✅" if counts[dep] == exp else "⚠️ "
        print(f"   {mark} {dep}: {counts[dep]} 条（预期 {exp}）")
    print(f"   注意：同一张图可能同时含多个废弃标签，条目数 ≠ 各类之和")
    print(f"   review_queue.json 已生成（{len(queue)} 条，reviewed=false）")


# ── --review-prepare ──────────────────────────────────────────────────────────
def cmd_review_prepare(limit: int) -> None:
    if not REVIEW_QUEUE_FILE.exists():
        print("❌ review_queue.json 不存在，请先运行 --build-review-queue")
        return

    queue         = load_json(REVIEW_QUEUE_FILE, [])
    pending_items = [e for e in queue if not e.get("reviewed", False)]

    if not pending_items:
        print("✅ 所有条目已完成回溯，无待处理项")
        return

    batch     = pending_items[:limit]
    batch_num = get_next_batch_num()
    out       = []

    for i, entry in enumerate(batch, 1):
        item_id = entry["item_id"]
        print(f"\n[{i}/{len(batch)}] 拉取 {item_id} 当前标签...")

        try:
            info_resp = eagle_get(f"/item/info?id={item_id}")
            info_data = info_resp.get("data", {})
            old_tags  = info_data.get("tags", [])
            name      = info_data.get("name", item_id)
            ext       = info_data.get("ext", "")
            file_path = str(LIB_PATH / "images" / f"{item_id}.info" / f"{name}.{ext}")
        except Exception as e:
            print(f"  ⚠️  Eagle API 异常，fallback 到打标时记录: {e}")
            old_tags  = entry.get("tags_at_tagging", [])
            name      = item_id
            file_path = ""

        tags_to_remove = [dep for dep in entry["deprecated_found"] if dep in old_tags]
        tags_to_keep   = [t for t in old_tags if t not in tags_to_remove]

        out.append({
            "index":            i,
            "item_id":          item_id,
            "file_path":        file_path,
            "name":             name,
            "old_tags":         old_tags,
            "deprecated_found": entry["deprecated_found"],
            "tags_to_remove":   tags_to_remove,
            "tags_to_add":      [],
            "tags_to_keep":     tags_to_keep,
        })
        print(f"  old_tags:       {old_tags}")
        print(f"  tags_to_remove: {tags_to_remove}")
        print(f"  tags_to_keep:   {tags_to_keep}")

    out_path = get_review_batch_path(batch_num)
    save_json(out_path, out)
    remaining = len(pending_items) - len(batch)
    print(f"\n✅ {out_path.name} 已生成（{len(out)} 张，等待填入 tags_to_add）")
    print(f"   填完后写入 review_batch_results_{batch_num}.json，再运行：")
    print(f"   python tag_real.py --review-apply --batch {batch_num}")
    print(f"   剩余待回溯: {remaining} 条")


# ── --review-apply ────────────────────────────────────────────────────────────
def cmd_review_apply(batch_num: str, confirm: bool) -> None:
    results_path = get_review_batch_path(batch_num, results=True)
    if not results_path.exists():
        print(f"❌ {results_path.name} 不存在")
        return

    results = load_json(results_path, [])
    if not results:
        print(f"❌ {results_path.name} 为空")
        return

    _, all_valid_tags, _ = load_tags()
    queue                = load_json(REVIEW_QUEUE_FILE, [])
    queue_map            = {e["item_id"]: e for e in queue}
    prog                 = ensure_prog_fields(load_json(PROGRESS_FILE, default_prog()))

    # diff 摘要
    print(f"\n── 本批 diff 摘要（batch {batch_num}，{len(results)} 张）{'─'*28}")
    for r in results:
        print(f"  [{r.get('index','?'):2}/{len(results)}] {r.get('item_id','?')}"
              f"   remove: {r.get('tags_to_remove', [])}"
              f"   add: {r.get('tags_to_add', [])}")
    print(f"{'─'*60}")

    if not confirm:
        ans = input("确认执行写回？(y/n): ").strip().lower()
        if ans != "y":
            print("已取消。")
            return

    success_count     = 0
    fail_count        = 0
    review_done_count = sum(1 for e in queue if e.get("reviewed", False))

    for r in results:
        item_id          = r.get("item_id", "")
        tags_to_remove   = r.get("tags_to_remove", [])
        tags_to_add      = r.get("tags_to_add", [])
        deprecated_found = r.get("deprecated_found", [])

        print(f"\n[{r.get('index','?')}/{len(results)}] {item_id}")

        # 白名单校验
        allowed = []
        for dep in deprecated_found:
            allowed += REPLACEMENT_WHITELIST.get(dep, [])
        invalid = [t for t in tags_to_add if t not in allowed]
        if invalid:
            msg = f"tags_to_add 含白名单外标签 {invalid}，跳过写回"
            print(f"  ❌ {msg}")
            log_review_warning(item_id, msg)
            fail_count += 1
            continue

        # 拉 Eagle 当前标签
        try:
            info_resp = eagle_get(f"/item/info?id={item_id}")
            current   = info_resp.get("data", {}).get("tags", [])
        except Exception as e:
            msg = f"Eagle API 拉标签失败: {e}"
            print(f"  ❌ {msg}")
            log_review_warning(item_id, msg)
            fail_count += 1
            continue

        # 差集替换
        final = (set(current) - set(tags_to_remove)) | set(tags_to_add)

        # 排异规则（只过滤新加的标签，不动原有标签）
        blocked_pfx = get_blocked_prefixes_from_tags(list(final))
        if blocked_pfx:
            dropped = [t for t in tags_to_add
                       if any(t.startswith(p + "-") for p in blocked_pfx)]
            if dropped:
                msg = (f"排异规则丢弃了 Claude 新加的标签: {dropped}"
                       f"（屏蔽前缀来自主类: {blocked_pfx}）")
                log_review_warning(item_id, msg)
                final -= set(dropped)

        # 写回 Eagle
        try:
            resp = eagle_post("/item/update", {"id": item_id, "tags": sorted(final)})
            if resp.get("status") != "success":
                raise RuntimeError(f"API 返回非 success: {resp}")
        except Exception as e:
            msg = f"Eagle API 写回失败: {e}"
            print(f"  ❌ {msg}")
            log_review_warning(item_id, msg)
            fail_count += 1
            continue

        print(f"  ✅ 写回成功 | remove: {tags_to_remove} | add: {tags_to_add} | 最终: {sorted(final)}")
        success_count += 1

        # 更新 progress.json record
        now_iso = datetime.now(timezone.utc).isoformat()
        for rec in prog.get("records", []):
            if rec["item_id"] == item_id:
                rec["reviewed_at"]         = now_iso
                rec["review_tag_version"]  = "2.0.1"
                rec["review_tags_removed"] = tags_to_remove
                rec["review_tags_added"]   = tags_to_add
                break

        # 更新 review_queue.json 状态位
        if item_id in queue_map:
            queue_map[item_id]["reviewed"]    = True
            queue_map[item_id]["reviewed_at"] = now_iso

        review_done_count += 1

        # 每 REVIEW_CHECKPOINT_EVERY 条触发检查点
        if review_done_count % REVIEW_CHECKPOINT_EVERY == 0:
            print(f"\n  [回溯检查点] 已完成 {review_done_count} 条...")
            save_json(PROGRESS_FILE, prog)
            save_json(REVIEW_QUEUE_FILE, list(queue_map.values()))
            run_checkpoint(prog)

    save_json(PROGRESS_FILE, prog)
    save_json(REVIEW_QUEUE_FILE, list(queue_map.values()))

    total_reviewed = sum(1 for e in queue_map.values() if e.get("reviewed", False))
    remaining      = len(queue_map) - total_reviewed
    print(f"\n{'━'*50}")
    print(f" batch {batch_num} 完成")
    print(f" ✅ 成功: {success_count} 张  ❌ 失败: {fail_count} 张"
          + (f"  →  详见 review_warnings.log" if fail_count else ""))
    print(f" 累计已回溯: {total_reviewed} / {len(queue_map)} 条")
    if remaining > 0:
        print(f" 下一步: python tag_real.py --review-prepare --limit 10")
    else:
        print(f" 🎉 全部 {len(queue_map)} 条已完成！运行 --review-report 生成汇总报告")
    print(f"{'━'*50}\n")


# ── --review-report ───────────────────────────────────────────────────────────
def cmd_review_report() -> None:
    queue = load_json(REVIEW_QUEUE_FILE, [])
    prog  = load_json(PROGRESS_FILE, default_prog())

    total   = len(queue)
    done    = sum(1 for e in queue if e.get("reviewed", False))
    pending = total - done

    if pending > 0:
        print(f"⚠️  还有 {pending} 条未完成回溯，报告将标注为部分完成")

    add_counter:    dict = {}
    remove_counter: dict = {}
    empty_light          = 0

    for rec in prog.get("records", []):
        if "reviewed_at" not in rec:
            continue
        removed = rec.get("review_tags_removed", [])
        added   = rec.get("review_tags_added",   [])
        for t in removed:
            remove_counter[t] = remove_counter.get(t, 0) + 1
        for t in added:
            add_counter[t] = add_counter.get(t, 0) + 1
        if "光-柔光" in removed and not any(t.startswith("光-") for t in added):
            empty_light += 1

    light_hits = {k: v for k, v in sorted(add_counter.items(), key=lambda x: -x[1])
                  if k.startswith("光-")}
    mat_hits   = {k: v for k, v in sorted(add_counter.items(), key=lambda x: -x[1])
                  if k.startswith("材-")}

    warnings_text = "（无）"
    if REVIEW_WARNINGS_LOG.exists():
        lines = REVIEW_WARNINGS_LOG.read_text(encoding="utf-8").strip().splitlines()
        warnings_text = f"{len(lines)} 条（详见 review_warnings.log）"

    vocab_text = "（无）"
    if VOCAB_FEEDBACK_FILE.exists():
        t = VOCAB_FEEDBACK_FILE.read_text(encoding="utf-8").strip()
        if t:
            vocab_text = t

    has_vocab_gap = VOCAB_FEEDBACK_FILE.exists() and VOCAB_FEEDBACK_FILE.stat().st_size > 0
    now_str       = datetime.now().strftime("%Y-%m-%d %H:%M")

    def fmt_hits(d: dict) -> str:
        return "\n".join(f"- {k}: {v} 次" for k, v in d.items()) or "（无）"

    report = f"""# Eagle 回溯修复报告
生成时间: {now_str}
回溯范围: 前 100 张（tag_version=1.0 → 2.0.1）

## 进度
- 总计待回溯: {total} 条
- 已完成: {done} 条
- 未完成: {pending} 条{"（全部完成 ✅）" if pending == 0 else "（部分完成 ⚠️）"}

## 废弃标签替换分布

### 移除统计
{chr(10).join(f"- {k}: {v} 次" for k, v in sorted(remove_counter.items(), key=lambda x: -x[1])) or "（无）"}

### 新增光标签命中次数
{fmt_hits(light_hits)}
- 光标签留空（找不到合适客观标签）: {empty_light} 张

### 新增材标签命中次数
{fmt_hits(mat_hits)}

## 警告记录
- review_warnings.log: {warnings_text}

## 词表缺口（vocab_feedback.md）
{vocab_text}

## 建议
{"- 词表缺口存在，建议发 v2.0.2（见 vocab_feedback.md）" if has_vocab_gap else "- 无明显词表缺口，暂不需要发 v2.0.2"}

## 下一步
- 前 100 张{"已全部" if pending == 0 else "部分"}升级到 v2.0.1
- 回到主线：python tag_real.py --prepare --limit 10（从第 101 张推进）
"""
    REVIEW_REPORT_FILE.write_text(report, encoding="utf-8")
    print(f"✅ REPORT_review.md 已生成")

    if pending == 0:
        _mark_review_done_in_state()
        _append_review_done_to_handoff(done)


def _mark_review_done_in_state() -> None:
    if not STATE_FILE.exists():
        return
    content = STATE_FILE.read_text(encoding="utf-8")
    if "前 100 张已全部升级到 v2.0.1" in content:
        return
    marker  = "- tag_real.py 真实打标脚本验证通过"
    new_line = "- **前 100 张已全部升级到 v2.0.1（回溯修复完成）**\n"
    STATE_FILE.write_text(content.replace(marker, new_line + marker), encoding="utf-8")
    print("✅ STATE.md 已标记回溯完成")


def _append_review_done_to_handoff(done: int) -> None:
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry   = (
        f"\n## 回溯修复完成 | {now_str}\n"
        f"- 前 100 张已全部升级到 v2.0.1\n"
        f"- 实际修复条目: {done} 条\n"
        f"- 下一步: 回主线 --prepare 从第 101 张推进\n"
    )
    with open(HANDOFF_FILE, "a", encoding="utf-8") as f:
        f.write(entry)
    print("✅ HANDOFF.md 已追加回溯完成记录")


# ── 格-标签分诊 ───────────────────────────────────────────────────────────────
def _load_all_records() -> list:
    prog   = load_json(PROGRESS_FILE, default_prog())
    recent = prog.get("records", [])
    archived: list = []
    for f in sorted(RECORDS_ARCHIVE_DIR.glob("records_*.json")):
        archived.extend(load_json(f, []))
    merged = {r["item_id"]: r for r in archived}
    merged.update({r["item_id"]: r for r in recent})
    return list(merged.values())


def cmd_build_ge_queue() -> None:
    records = _load_all_records()
    queue = [
        {
            "item_id":      rec["item_id"],
            "name":         "",
            "current_tags": rec.get("tags_added", []),
            "image_path":   None,
        }
        for rec in records
    ]
    save_json(GE_REVIEW_QUEUE_FILE, queue)
    prog         = load_json(PROGRESS_FILE, default_prog())
    recent_cnt   = len(prog.get("records", []))
    archived_cnt = sum(
        len(load_json(f, []))
        for f in RECORDS_ARCHIVE_DIR.glob("records_*.json")
    )
    print(f"\n✅ --build-ge-queue 完成")
    print(f"   progress.json records:   {recent_cnt}")
    print(f"   archive/records records: {archived_cnt}")
    print(f"   ge_review_queue.json 已生成（{len(queue)} 条）")


def _get_ban_tags() -> list:
    return load_json(TAGS_FILE, {}).get("tags", {}).get("版", [])


def _triage_one(tags: set, ban_tags: list) -> tuple:
    """Returns (bucket, rule_hit, candidates_ge, candidates_ban, skip_reason)"""
    # S1: already has any 格- tag
    ge_present = [t for t in tags if t.startswith("格-")]
    if ge_present:
        return ("skip", "S1", None, None, f"S1: already has {', '.join(ge_present)}")
    # S2
    if "类-实景参考" in tags:
        return ("skip", "S2", None, None, "S2: 类-实景参考")
    # S3
    if "类-照片" in tags or "类-摄影" in tags:
        hit = "类-照片" if "类-照片" in tags else "类-摄影"
        return ("skip", "S3", None, None, f"S3: {hit}")
    # S4
    if "类-游戏截图" in tags:
        return ("skip", "S4", None, None, "S4: 游戏截图本身即游戏归属")
    # U1
    if "类-UI" in tags or "类-排版" in tags:
        return ("need", "U1", [], ban_tags, None)
    # R1
    if "题-赛博朋克" in tags:
        return ("need", "R1", ["格-赛博朋克2077", "格-命运2", "格-控制"], None, None)
    # R2
    if "题-都市幻想" in tags or "题-近未来" in tags:
        return ("need", "R2", ["格-绝区零", "格-控制", "格-VA-11 HALL-A"], None, None)
    # R3
    if "题-剑与魔法" in tags and ("角-立绘" in tags or "类-角色原画" in tags):
        return ("need", "R3", ["格-原神", "格-塞尔达王国之泪", "格-魂系"], None, None)
    # R4
    if "题-科幻" in tags and ("物-机甲" in tags or "类-机械设定" in tags):
        return ("need", "R4", ["格-装甲核心6", "格-质量效应", "格-异形:隔离", "格-命运2"], None, None)
    # R5（修订：加入题-后启示录）
    if "题-末世" in tags or "题-废土" in tags or "题-后启示录" in tags:
        return ("need", "R5", ["格-辐射系列", "格-逃离塔科夫", "格-死亡搁浅"], None, None)
    # R6
    if "题-恐怖" in tags or "氛-诡异" in tags:
        return ("need", "R6", ["格-异形:隔离", "格-控制", "格-雨世界"], None, None)
    # R7
    if "风-像素" in tags or "风-2D横版" in tags:
        return ("need", "R7", ["格-Hades", "格-雨世界", "格-VA-11 HALL-A"], None, None)
    # R8
    if "题-奇幻" in tags:
        return ("need", "R8", ["格-原神", "格-塞尔达王国之泪", "格-魂系", "格-Hades"], None, None)
    # R9
    if "题-复古未来" in tags:
        return ("need", "R9", ["格-辐射系列", "格-极乐迪斯科", "格-VA-11 HALL-A"], None, None)
    # R10
    if "风-日系" in tags:
        return ("need", "R10", ["格-明日方舟", "格-原神", "格-绝区零"], None, None)
    # fallback
    return ("uncertain", None, None, None, None)


def cmd_triage(dry_run: bool = False) -> None:
    if not GE_REVIEW_QUEUE_FILE.exists():
        print("❌ ge_review_queue.json 不存在，请先运行 --build-ge-queue")
        return

    queue    = load_json(GE_REVIEW_QUEUE_FILE, [])
    ban_tags = _get_ban_tags()

    need_list: list      = []
    skip_list: list      = []
    uncertain_list: list = []
    rule_counts: dict    = {}

    for entry in queue:
        tags   = set(entry.get("current_tags", []))
        bucket, rule, cands_ge, cands_ban, skip_reason = _triage_one(tags, ban_tags)
        rule_counts[rule] = rule_counts.get(rule, 0) + 1

        if bucket == "skip":
            skip_list.append({
                "item_id":      entry["item_id"],
                "current_tags": entry.get("current_tags", []),
                "skip_reason":  skip_reason,
            })
        elif bucket == "need":
            need_list.append({
                "item_id":        entry["item_id"],
                "name":           entry.get("name", ""),
                "current_tags":   entry.get("current_tags", []),
                "rule_hit":       rule,
                "candidates_ge":  cands_ge,
                "candidates_ban": cands_ban,
                "image_path":     entry.get("image_path"),
            })
        else:
            uncertain_list.append({
                "item_id":      entry["item_id"],
                "current_tags": entry.get("current_tags", []),
                "image_path":   entry.get("image_path"),
            })

    total = len(queue)
    print(f"\n{'━'*52}")
    print(f" 格-标签分诊 {'[DRY-RUN]' if dry_run else '[实际写入]'}")
    print(f"{'━'*52}")
    print(f" 总计:      {total} 条")
    print(f" need:      {len(need_list)} 条（需看图）")
    print(f" skip:      {len(skip_list)} 条（无需补）")
    print(f" uncertain: {len(uncertain_list)} 条（兜底看图）")
    print(f"\n 规则命中分布:")
    for rule_key in ["S1", "S2", "S3", "S4", "U1", "R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "R9", "R10"]:
        cnt = rule_counts.get(rule_key, 0)
        if cnt:
            print(f"   {rule_key:4s}: {cnt}")
    unc_cnt = rule_counts.get(None, 0)
    if unc_cnt:
        print(f"   uncertain: {unc_cnt}")

    if not dry_run:
        save_json(GE_TRIAGE_NEED_FILE, need_list)
        save_json(GE_TRIAGE_SKIP_FILE, skip_list)
        save_json(GE_TRIAGE_UNCERTAIN_FILE, uncertain_list)
        print(f"\n ✅ 已写入 ge_need.json / ge_skip.json / ge_uncertain.json")

    _write_ge_triage_report(total, need_list, skip_list, uncertain_list, rule_counts, dry_run)
    print(f" ✅ REPORT_ge_triage.md 已生成")
    print(f"{'━'*52}\n")


def _write_ge_triage_report(
    total: int,
    need_list: list,
    skip_list: list,
    uncertain_list: list,
    rule_counts: dict,
    dry_run: bool,
) -> None:
    now_str   = datetime.now().strftime("%Y-%m-%d %H:%M")
    dr_suffix = "  [DRY-RUN]" if dry_run else ""

    need_samples: dict = {}
    for e in need_list:
        r = e["rule_hit"]
        if r not in need_samples:
            need_samples[r] = e

    skip_samples: dict = {}
    for e in skip_list:
        r = e["skip_reason"].split(":")[0].strip()
        if r not in skip_samples:
            skip_samples[r] = e

    need_sample_md = ""
    for rule_key in ["U1", "R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "R9", "R10"]:
        if rule_key in need_samples:
            e    = need_samples[rule_key]
            cands = e.get("candidates_ge") or e.get("candidates_ban") or []
            tags_preview = ", ".join(e["current_tags"][:5])
            if len(e["current_tags"]) > 5:
                tags_preview += "..."
            need_sample_md += (
                f"- **{rule_key}** `{e['item_id']}`  \n"
                f"  标签: `{tags_preview}`  \n"
                f"  候选: `{', '.join(cands)}`\n"
            )

    skip_sample_md = ""
    for rule_key in ["S1", "S2", "S3", "S4"]:
        if rule_key in skip_samples:
            e = skip_samples[rule_key]
            tags_preview = ", ".join(e["current_tags"][:4])
            skip_sample_md += (
                f"- **{rule_key}** `{e['item_id']}`  \n"
                f"  原因: `{e['skip_reason']}`  \n"
                f"  标签: `{tags_preview}`\n"
            )

    rule_dist_rows = ""
    for rule_key in ["S1", "S2", "S3", "S4", "U1", "R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "R9", "R10"]:
        cnt = rule_counts.get(rule_key, 0)
        rule_dist_rows += f"| {rule_key} | {cnt} |\n"
    rule_dist_rows += f"| uncertain (兜底) | {rule_counts.get(None, 0)} |\n"

    report = f"""# REPORT_ge_triage — 格-标签分诊报告
生成时间: {now_str}{dr_suffix}

---

## 一、分流汇总

| 类别 | 数量 | 说明 |
|------|------|------|
| **总计** | {total} | ge_review_queue.json 全部条目 |
| need（需看图） | {len(need_list)} | 规则命中，提供 格-/版- 候选 |
| skip（无需补） | {len(skip_list)} | 规则判定已覆盖或不适用 |
| uncertain（兜底） | {len(uncertain_list)} | 无规则命中，需自由看图 |

---

## 二、规则命中分布

| 规则 | 命中数 |
|------|--------|
{rule_dist_rows}
---

## 三、抽样展示

### need 类（各规则取 1 条）

{need_sample_md.strip() or '（无命中）'}

### skip 类（各规则取 1 条）

{skip_sample_md.strip() or '（无命中）'}

---

## 四、边界情况说明

- **判定顺序**：S1→S2→S3→S4→U1→R1→R2→R3→R4→R5→R6→R7→R8→R9→R10→uncertain，命中即停
- **R3 vs R8**：题-奇幻 且含"剑与魔法+角色"条件 → R3 先命中；仅含 题-奇幻 → R8
- **S4**：类-游戏截图 → skip，游戏截图本身已隐含游戏归属，无需补 格-
- **R5 修订**：加入 题-后启示录 触发条件
- **R9**：题-复古未来 → 格-辐射系列 / 格-极乐迪斯科 / 格-VA-11 HALL-A
- **R10**：风-日系 → 格-明日方舟 / 格-原神 / 格-绝区零
- **U1 互斥**：含 类-UI/排版 的图只判 版-，不判 格-（UI 图游戏归属模糊）
- **uncertain 含义**：未命中任何规则，需 Claude 看图后自由选 格- 或确认无需补
- **image_path**：当前全部为 null，需后续 --ge-prepare 步骤填充后才能看图
"""
    GE_TRIAGE_REPORT_FILE.write_text(report, encoding="utf-8")


# ── --apply-batch --batch ge_NN：写回 ge 批次决策 ────────────────────────────
def cmd_ge_apply_batch(num_str: str, dry_run: bool = False) -> None:
    """Apply ge_batch_results_{num_str}.json back to Eagle.
    Items must be in ge_need/uncertain. Empty tags_to_add → reviewed, no write.
    """
    batch_file = BASE_DIR / f"ge_batch_results_{num_str}.json"
    if not batch_file.exists():
        print(f"❌ 找不到 {batch_file.name}")
        return

    batch = load_json(batch_file, [])
    if not batch:
        print(f"❌ {batch_file.name} 为空")
        return

    need_list      = load_json(GE_TRIAGE_NEED_FILE, [])
    uncertain_list = load_json(GE_TRIAGE_UNCERTAIN_FILE, [])
    skip_list      = load_json(GE_TRIAGE_SKIP_FILE, [])
    valid_ids      = {e["item_id"] for e in need_list + uncertain_list}
    s1_ids         = {e["item_id"] for e in skip_list
                      if e.get("skip_reason", "").startswith("S1")}

    # Validate against all processed records (recent + archived)
    all_records    = _load_all_records()
    all_record_ids = {r["item_id"] for r in all_records}

    mode_str = "[DRY-RUN]" if dry_run else "[实际写入]"
    print(f"\n{'━'*52}")
    print(f" ge-apply-batch {mode_str}")
    print(f"{'━'*52}")
    print(f" 批次文件: {batch_file.name}  ({len(batch)} 条)")

    not_in_records = [e["item_id"] for e in batch if e.get("item_id") not in all_record_ids]
    not_in_queue   = [e["item_id"] for e in batch if e.get("item_id") not in valid_ids]
    no_change_cnt  = sum(1 for e in batch if not e.get("tags_to_add"))
    write_cnt      = len(batch) - no_change_cnt

    if not_in_records:
        print(f" [警告] {len(not_in_records)} 条不在 progress records 中: {not_in_records[:5]}")
    else:
        print(f" ✅ 全部 {len(batch)} 条均在 progress records 中")
    if not_in_queue:
        print(f" [注意] {len(not_in_queue)} 条不在 ge_need/uncertain（可能已重新分诊）")
    print(f" 无变更（[]）: {no_change_cnt} 条 → 标记已检视，不写 Eagle")
    print(f" 需写回:       {write_cnt} 条")
    print()

    written_count = 0
    error_count   = 0
    errors        = []
    ge_added_ids  = set()
    ban_added_ids = set()

    for i, entry in enumerate(batch, 1):
        item_id     = entry.get("item_id", "")
        tags_to_add = entry.get("tags_to_add", [])

        if item_id not in valid_ids:
            continue

        if not tags_to_add:
            if dry_run:
                print(f"  [{i:03d}] {item_id}  已检视，无新增")
            continue

        try:
            info     = eagle_get(f"/item/info?id={item_id}")
            old_tags = info.get("data", {}).get("tags", [])
        except Exception as e:
            print(f"  [{i:03d}] ❌ {item_id} 查询失败: {e}")
            error_count += 1
            errors.append({"item_id": item_id, "error": str(e)})
            continue

        new_tags = [t for t in tags_to_add if t not in old_tags]
        if not new_tags:
            if dry_run:
                print(f"  [{i:03d}] {item_id}  标签已存在: {tags_to_add}")
            continue

        merged = list(old_tags) + new_tags

        if dry_run:
            print(f"  [{i:03d}] {item_id}  +{new_tags}  (旧:{len(old_tags)} → 合并:{len(merged)})")
            written_count += 1
        else:
            try:
                resp = eagle_post("/item/update", {"id": item_id, "tags": merged})
                if resp.get("status") != "success":
                    print(f"  [{i:03d}] ❌ {item_id}: {resp}")
                    error_count += 1
                    errors.append({"item_id": item_id, "error": str(resp)})
                    continue
                print(f"  [{i:03d}] ✅ {item_id}  +{new_tags}")
                written_count += 1
            except Exception as e:
                print(f"  [{i:03d}] ❌ {item_id}: {e}")
                error_count += 1
                errors.append({"item_id": item_id, "error": str(e)})
                continue

        for t in new_tags:
            if t.startswith("格-"):
                ge_added_ids.add(item_id)
            elif t.startswith("版-"):
                ban_added_ids.add(item_id)

    # Coverage: S1 already had 格- + what this batch added
    total_queue   = len(need_list) + len(uncertain_list) + len(skip_list)
    covered_count = len(s1_ids) + len(ge_added_ids) + len(ban_added_ids)
    coverage_pct  = covered_count / total_queue * 100 if total_queue else 0

    print(f"\n{'━'*52}")
    print(f" 结果汇总 {mode_str}")
    print(f"{'━'*52}")
    print(f" 写回成功: {written_count}")
    print(f" 无变更:   {no_change_cnt + (write_cnt - written_count - error_count)}")
    print(f" 错误:     {error_count}")
    if errors:
        print(f"\n 异常清单:")
        for err in errors:
            print(f"   {err['item_id']}: {err['error']}")
    print(f"\n 格-/版- 覆盖率（{total_queue} 条 ge 队列）:")
    print(f"   S1（原有格-）:  {len(s1_ids)}")
    print(f"   本批新增格-:    {len(ge_added_ids)} 条")
    print(f"   本批新增版-:    {len(ban_added_ids)} 条")
    print(f"   合计有效覆盖:   {covered_count} / {total_queue} = {coverage_pct:.1f}%")
    print(f"   注：有 版- 旧标签的 [] 条目未统计，覆盖率为下限估算")
    print(f"{'━'*52}\n")


# ── --ge-prepare：缩略图网格生成 ──────────────────────────────────────────────
GE_GRIDS_DIR       = BASE_DIR / "archive" / "ge_grids"
GE_GRID_INDEX_FILE = BASE_DIR / "archive" / "ge_grids" / "ge_grid_index.json"

GRID_COLS       = 4
GRID_ROWS       = 4
GRID_CELL_PX    = 256
GRID_GAP_PX     = 8
GRID_LABEL_H_PX = 18


def _resolve_item_path(item_id: str):
    """Fetch item info from Eagle API and return local file path, or None on failure."""
    try:
        info = eagle_get(f"/item/info?id={item_id}")
        data = info.get("data", {})
        name = data.get("name", item_id)
        ext  = data.get("ext", "")
        if not ext:
            return None
        return LIB_PATH / "images" / f"{item_id}.info" / f"{name}.{ext}"
    except Exception as e:
        print(f"  [警告] Eagle API 查询 {item_id} 失败: {e}")
        return None


def _make_grid(entries: list, output_path: Path) -> list:
    """
    Build a 4×4 thumbnail grid from up to 16 entries.
    Returns list of slot dicts used (for index file).
    Returns empty list if PIL unavailable.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("  [错误] PIL 未安装，请运行: pip install Pillow")
        return []

    cells_per_grid = GRID_COLS * GRID_ROWS
    slots = entries[:cells_per_grid]

    total_w = GRID_COLS * GRID_CELL_PX + (GRID_COLS - 1) * GRID_GAP_PX
    total_h = GRID_ROWS * GRID_CELL_PX + (GRID_ROWS - 1) * GRID_GAP_PX + GRID_LABEL_H_PX

    canvas = Image.new("RGB", (total_w, total_h), color=(40, 40, 40))
    draw   = ImageDraw.Draw(canvas)

    try:
        font = ImageFont.truetype("arial.ttf", 11)
    except Exception:
        font = ImageFont.load_default()

    slot_records = []
    for idx, entry in enumerate(slots):
        col = idx % GRID_COLS
        row = idx // GRID_COLS
        x0  = col * (GRID_CELL_PX + GRID_GAP_PX)
        y0  = row * (GRID_CELL_PX + GRID_GAP_PX) + GRID_LABEL_H_PX

        item_id   = entry["item_id"]
        img_path  = entry.get("_resolved_path")
        label_txt = f"{idx+1:02d}_{item_id[:6]}"

        # thumbnail
        cell_img = None
        if img_path and Path(img_path).exists():
            try:
                cell_img = Image.open(img_path).convert("RGB")
                cell_img.thumbnail((GRID_CELL_PX, GRID_CELL_PX), Image.LANCZOS)
            except Exception as e:
                print(f"  [警告] 无法打开图片 {img_path}: {e}")
                cell_img = None

        if cell_img:
            # centre within cell
            px = x0 + (GRID_CELL_PX - cell_img.width)  // 2
            py = y0 + (GRID_CELL_PX - cell_img.height) // 2
            canvas.paste(cell_img, (px, py))
        else:
            draw.rectangle([x0, y0, x0 + GRID_CELL_PX - 1, y0 + GRID_CELL_PX - 1],
                           fill=(80, 80, 80), outline=(120, 120, 120))
            draw.text((x0 + 4, y0 + GRID_CELL_PX // 2 - 6), "N/A", fill=(180, 180, 180), font=font)

        # label: white bg + black text in top-left corner
        bbox = draw.textbbox((0, 0), label_txt, font=font)
        lw   = bbox[2] - bbox[0] + 4
        lh   = bbox[3] - bbox[1] + 2
        draw.rectangle([x0, y0, x0 + lw, y0 + lh], fill=(255, 255, 255))
        draw.text((x0 + 2, y0 + 1), label_txt, fill=(0, 0, 0), font=font)

        slot_records.append({
            "slot":           idx + 1,
            "item_id":        item_id,
            "candidates_ge":  entry.get("candidates_ge"),
            "candidates_ban": entry.get("candidates_ban"),
        })

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(str(output_path))
    return slot_records


def cmd_ge_prepare() -> None:
    need_list      = load_json(GE_TRIAGE_NEED_FILE, [])
    uncertain_list = load_json(GE_TRIAGE_UNCERTAIN_FILE, [])

    if not need_list and not uncertain_list:
        print("❌ ge_need.json 和 ge_uncertain.json 均为空，请先运行 --triage")
        return

    print(f"  ge_need.json:      {len(need_list)} 条")
    print(f"  ge_uncertain.json: {len(uncertain_list)} 条")

    GE_GRIDS_DIR.mkdir(parents=True, exist_ok=True)

    grid_index: dict = {}
    cells_per_grid   = GRID_COLS * GRID_ROWS

    def _process_bucket(entries: list, prefix: str) -> int:
        """Resolve paths, build grids, return grid count."""
        print(f"\n  [路径解析] {prefix} …")
        for entry in entries:
            p = _resolve_item_path(entry["item_id"])
            entry["_resolved_path"] = str(p) if p else None

        grid_count = 0
        for chunk_start in range(0, len(entries), cells_per_grid):
            chunk      = entries[chunk_start : chunk_start + cells_per_grid]
            grid_num   = chunk_start // cells_per_grid + 1
            fname      = f"{prefix}_{grid_num:03d}.png"
            out_path   = GE_GRIDS_DIR / fname
            print(f"  → 生成 {fname}（{len(chunk)} 格）…", end=" ", flush=True)
            slots = _make_grid(chunk, out_path)
            if slots:
                grid_index[fname] = slots
                print("✅")
            else:
                print("❌ (PIL 失败)")
            grid_count += 1
        return grid_count

    need_grids      = _process_bucket(need_list,      "need")
    uncertain_grids = _process_bucket(uncertain_list, "uncertain")

    # strip internal helper key before saving
    for entry in need_list + uncertain_list:
        entry.pop("_resolved_path", None)

    save_json(GE_GRID_INDEX_FILE, grid_index)

    print(f"\n{'━'*52}")
    print(f" --ge-prepare 完成")
    print(f"{'━'*52}")
    print(f" need 网格:      {need_grids} 张")
    print(f" uncertain 网格: {uncertain_grids} 张")
    if need_grids:
        first = GE_GRIDS_DIR / "need_001.png"
        print(f" 第一张路径:     {first}")
    print(f" 索引文件:       {GE_GRID_INDEX_FILE}")
    print(f"{'━'*52}\n")


# ── --sync ────────────────────────────────────────────────────────────────────
def cmd_sync() -> None:
    t0 = time.time()
    DERIVED_DIR.mkdir(exist_ok=True)

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ── load config ──────────────────────────────────────────────────────────
    tags_data   = load_json(CONFIG_DIR / "tags.json", {})
    rules_data  = load_json(CONFIG_DIR / "rules.json", {})
    workflow    = load_json(CONFIG_DIR / "workflow.json", {})
    prefs       = load_json(CONFIG_DIR / "preferences.json", {})
    changelog_path = CONFIG_DIR / "CHANGELOG.md"
    changelog_tail = ""
    if changelog_path.exists():
        lines = changelog_path.read_text(encoding="utf-8").splitlines()
        entries = [l for l in lines if l.startswith("- ")]
        changelog_tail = "\n".join(entries[-5:])

    tags_ver    = tags_data.get("version", "unknown")
    tags_by_pfx = tags_data.get("tags", {})
    total_tags  = sum(len(v) for v in tags_by_pfx.values())
    prefix_cnt  = len(tags_by_pfx)

    prog        = ensure_prog_fields(load_json(PROGRESS_FILE, default_prog()))
    total_proc  = prog.get("total_processed", 0)
    lib_total   = workflow.get("library_total", LIBRARY_TOTAL)
    batch_size  = workflow.get("batch_size", BATCH_SIZE)
    chk_every   = workflow.get("checkpoint_every_n", CHECKPOINT_EVERY)

    sdata       = load_json(SUGGESTED_FILE, {"suggested": {}})
    smap        = sdata.get("suggested", {})
    sug_pending = [k for k, v in smap.items() if v.get("count", 0) >= 3]

    exc_data    = load_json(EXCEPTIONS_FILE, [])
    exc_count   = len(exc_data)

    # prefix breakdown table
    pfx_table_rows = "\n".join(
        f"| {pfx}- | {len(tags_by_pfx[pfx])} |" for pfx in tags_by_pfx
    )

    exc_warning = ""
    if exc_count >= 20:
        exc_warning = f"\n⚠️ exceptions.json 累计 {exc_count} 条，建议集中处理\n"

    header = (
        "<!-- AUTO-GENERATED FROM /config/. DO NOT EDIT.\n"
        f"     Last sync: {now_str} from tags.json v{tags_ver} -->\n\n"
    )

    priorities = prefs.get("priorities", {})
    ban_txt    = load_prompt("版.txt")

    # ── derived/CLAUDE.md ─────────────────────────────────────────────────────
    claude_md = header + f"""# Eagle 素材库打标 — Claude Code 启动手册

{exc_warning}
## 项目身份

- 用户角色：{prefs.get('user_role', '')}
- 打标意图：{prefs.get('intent', '')}
- 词表版本：tags.json v{tags_ver}，{total_tags} 个标签，{prefix_cnt} 个前缀
- 库总量：{lib_total} 张

## 启动顺序（固定）

1. 读 `derived/CLAUDE.md`（本文件）
2. 读 `config/tags.json`（完整词表）
3. 读 `progress.json`（已处理 ID，打标时跳过）
4. 读 `suggested_tags.json`（待审建议标签，先展示给用户）
5. 按用户指示继续批量流程（prepare → 读图输出 JSON → apply-batch）

## 标签选择优先级

**格-（最高权重，主检索入口）**
{priorities.get('格-', '')}

**版-（次高权重）**
{priorities.get('版-', '')}

**风-**
{priorities.get('风-', '')}

禁止维度：{', '.join(prefs.get('forbidden_dimensions', []))}

## 排异规则

- 类-UI / 类-排版 / 类-实景参考：屏蔽 光/镜/氛/场 前缀
- 类-UI / 类-排版：放行 格-/版-

## 格- 候选缩窄规则（v2.1 词表，rules_engine.py / candidates_for_ge）

R1: 题-赛博朋克 → [格-赛博朋克2077, 格-命运2, 格-控制]
R2: 题-都市幻想 / 题-近未来 → [格-绝区零, 格-控制, 格-VA-11 HALL-A]
R3: 题-剑与魔法 + (角-立绘 / 类-角色原画) → [格-塞尔达王国之泪, 格-魂系]
R4: 题-硬科幻 + (物-机甲 / 类-道具设定) → [格-装甲核心6, 格-质量效应, 格-异形:隔离, 格-命运2]
R5: 题-末日废土 → [格-辐射系列, 格-逃离塔科夫, 格-死亡搁浅]
R6: 氛-诡异 / 氛-恐怖 → [格-异形:隔离, 格-控制, 格-雨世界]
R7: 题-复古未来 → [格-辐射系列, 格-极乐迪斯科, 格-VA-11 HALL-A]
R8: 风-日系 → [格-明日方舟, 格-绝区零]
未命中 → 自由从全部 格- 中选，拿不准则不补。

S1: 已含任意 格- → skip
S2: 类-实景参考 → skip
S3: 类-照片 / 类-摄影 → skip
S4: 类-游戏截图 → skip

{ban_txt}
## 强制自检规则（每张图打标后必走）

打标输出前，对 tags_to_add 每个标签：
1. 完整存在于 config/tags.json？（前缀+内容都要对）
2. 不存在 → 立刻移出 tags_to_add
3. 概念有价值 → 追加 suggested 字段
4. 无价值 → 丢弃

**错误示范（绝对禁止）：**
- config/tags.json 有"构-"前缀但无"构-俯视" → 不能写"构-俯视"
- 有"题-末日废土"但无"题-末世" → 不能写"题-末世"
- 有"类-角色原画"但无"类-角色设定" → 不能写"类-角色设定"
- 有"类-概念图"但无"类-场景设定" → 不能写"类-场景设定"
- 有"风-"前缀但"风-"下无具体作品名 → 风-不含作品名，作品走格-
- 格-原神不在 v2.1 词表 → 不能写"格-原神"

**正确做法：**
- 俯视构图 → 选 tags.json 里已有的近义构标签，无则不补构
- 末世废土题材 → 写"题-末日废土"（已有），不写"题-末世"
- 角色设定图 → 写"类-角色原画"，不写"类-角色设定"
- 日系风格明确对应游戏 → 格-明日方舟 或 格-绝区零（R8），不自造格-原神

## 词表外概念

词表无法表达的概念 → 写入 suggested 字段，不写入 tags_to_add。
suggested 累计 count≥3 由用户决定是否升入词表。

## 异常上报

无法归类时：tags_to_add 留空 []，不在正文写长篇解释。
脚本自动写入 exceptions.json（当前 {exc_count} 条）。
⚠️ exceptions.json 累计 ≥ 20 条时强制停机。

## 输出格式

```json
[{{"item_id": "xxx", "tags_to_add": ["前缀-内容"], "suggested": ["新概念"]}}]
```

## 安全约束

- 一张图只做一次视觉分析
- 写回前脚本自动合并旧标签
- 每 {chk_every} 张自动触发检查点
- 当前进度：{total_proc} / {lib_total} 张
"""

    (DERIVED_DIR / "CLAUDE.md").write_text(claude_md, encoding="utf-8")

    # ── derived/STATE.md ──────────────────────────────────────────────────────
    records    = prog.get("records", [])
    last       = records[-1] if records else {}
    last_id    = last.get("item_id", "—")
    batch_num  = prog.get("batch_counter", 0)

    sug_list_str = str(list(smap.keys())[:10]) if smap else "（无）"
    sug_pend_str = str(sug_pending) if sug_pending else "（无）"

    # 漂移说明：last_checkpoint_total 与 current total 差值 ≥1 时显示
    last_chk = prog.get("last_checkpoint_total", 0)
    drift_note = ""
    if total_proc - last_chk >= 1:
        drift_note = f"\n> Note: last checkpoint at {last_chk}, current total {total_proc}\n"

    state_md = header + f"""# Eagle 素材库打标签项目 — 当前状态

{exc_warning}
{drift_note}最后同步：{now_str}　　进度：{total_proc} / {lib_total} 张

---

## 当前进度

- **已处理**：{total_proc} / {lib_total} 张（{total_proc/lib_total*100:.2f}%）
- **最后 item_id**：`{last_id}`
- **当前批次号**：{batch_num}

---

## 词表统计（config/tags.json v{tags_ver}）

- 标签总数：**{total_tags} 个 / {prefix_cnt} 个前缀**

| 前缀 | 数量 |
|------|------|
{pfx_table_rows}

---

## 待审建议标签（suggested_tags.json，count≥3）

{sug_pend_str}

所有 suggested 条目（共 {len(smap)} 个）：{sug_list_str}

---

## exceptions.json

累计 {exc_count} 条{'（建议集中处理）' if exc_count >= 20 else ''}

---

## 下一步待办

1. `python tag_real.py --prepare --limit {batch_size}`
2. 读全部图，输出 JSON 写入 batch_results_NNN.json
3. `python tag_real.py --apply-batch`
4. 每 {chk_every} 张自动检查点

---

## 踩过的坑（简版）

| 坑 | 解决方案 |
|---|---|
| 系统代理劫持 localhost | ProxyHandler({{}}) 绕过 |
| limit 小时分页截断 | 统一 limit=1000 |
| Eagle API 无总数字段 | limit=25000 探底得 {lib_total} |
| orderBy=-CREATEDATE 排序反了 | 去掉 orderBy |
| btime=0 老素材 | 改用 modificationTime |
"""

    (DERIVED_DIR / "STATE.md").write_text(state_md, encoding="utf-8")

    # ── derived/HANDOFF.md ────────────────────────────────────────────────────
    handoff_md = header + f"""# Eagle 打标项目 — 新对话开场交接文档

{exc_warning}
> 新会话开始时只需粘贴本文件，无需其他文档。

---

## 当前进度

- 已处理：**{total_proc} / {lib_total}** 张（{total_proc/lib_total*100:.2f}%）
- 批次号：{batch_num}
- 最后 item_id：`{last_id}`

---

## 当前词表版本与近期变更

tags.json v{tags_ver}，{total_tags} 标签 / {prefix_cnt} 前缀

最近 5 条变更：
{changelog_tail}

---

## 用户偏好（config/preferences.json 全量）

- 角色：{prefs.get('user_role', '')}
- 意图：{prefs.get('intent', '')}
- 格- 权重：{priorities.get('格-', '')}
- 版- 权重：{priorities.get('版-', '')}
- 风- 权重：{priorities.get('风-', '')}
- 禁止维度：{', '.join(prefs.get('forbidden_dimensions', []))}
- 食物素材：{prefs.get('food_assets', '')}

---

## 已知坑（手工维护，超 8 条时归档到 docs/pitfalls.md）

1. 系统代理劫持 localhost → ProxyHandler({{}}) 绕过
2. limit 小时分页截断 → 统一 limit=1000
3. Eagle API 无总数字段 → limit=25000 探底
4. orderBy=-CREATEDATE 排序反了 → 去掉 orderBy
5. btime=0 老素材 → 改用 modificationTime
6. /api/v2/ 端点不存在 → 用 /api/ 前缀

---

## 待处理清单（不主动 surface）

- suggested_tags.json count≥3 待审：{len(sug_pending)} 个
- exceptions.json 累计：{exc_count} 条
- 词表外概念建议：读 suggested_tags.json

---

## 下一步入口

```bash
python tag_real.py --prepare --limit {batch_size}
# 读图，输出 batch_results_NNN.json
python tag_real.py --apply-batch
```

或用 run.bat：
```
run prepare {batch_size}
run apply
```
"""

    (DERIVED_DIR / "HANDOFF.md").write_text(handoff_md, encoding="utf-8")

    elapsed = time.time() - t0
    print(f"✅ --sync 完成（{elapsed:.2f}s）")
    print(f"   derived/CLAUDE.md  derived/STATE.md  derived/HANDOFF.md")
    print(f"   tags v{tags_ver} · {total_tags} 标签 / {prefix_cnt} 前缀 · 进度 {total_proc}/{lib_total}")
    if exc_count >= 20:
        print(f"   ⚠️  exceptions.json 累计 {exc_count} 条，建议集中处理")


# ── --test-llm ────────────────────────────────────────────────────────────────
def cmd_test_llm(item_id: str) -> None:
    """单张测试：调 mimo，结果写 reports/test_llm_<ID>.json，终端打印摘要。"""
    REPORTS_DIR.mkdir(exist_ok=True)

    # a) 从 Eagle 拉取 item 信息
    try:
        data = eagle_get(f"/item/info?id={item_id}")
    except Exception as e:
        print(f"❌ Eagle API 请求失败: {e}")
        return
    item = data.get("data") or data
    if not item or not isinstance(item, dict):
        print(f"❌ 未找到 item: {item_id}")
        return

    existing_tags = item.get("tags", [])

    # b-c) 读图 + 组装 messages
    try:
        messages = build_messages(item)
    except Exception as e:
        print(f"❌ build_messages 失败: {e}")
        return

    # d) 调用 mimo
    t0 = time.time()
    result = call_mimo(messages)
    if result is None:
        print(f"❌ call_mimo 失败（重试耗尽）")
        return
    elapsed_ms = int((time.time() - t0) * 1000)

    new_tags = result["tags"]
    usage    = result["usage"]

    # e) 写 JSON 报告（不动 progress.json / batch_results）
    out = {
        "item_id":      item_id,
        "model":        MIMO_MODEL,
        "existing_tags": existing_tags,
        "new_tags":     new_tags,
        "raw_response": result["raw"],
        "usage":        usage,
        "elapsed_ms":   elapsed_ms,
    }
    report_path = REPORTS_DIR / f"test_llm_{item_id}.json"
    save_json(report_path, out)
    print(f"✅ 报告已写入: {report_path.relative_to(BASE_DIR)}")

    # f) 终端简表
    intersection = sorted(set(existing_tags) & set(new_tags))
    print(f"\n{'─' * 52}")
    print(f"  item_id        : {item_id}")
    print(f"  model          : {MIMO_MODEL}")
    print(f"  旧标签数        : {len(existing_tags)}")
    print(f"  新标签数        : {len(new_tags)}")
    print(f"  交集 ({len(intersection)})       : {intersection}")
    print(f"  耗时            : {elapsed_ms} ms")
    print(f"  prompt_tokens   : {usage['prompt_tokens']}")
    print(f"  completion_tokens: {usage['completion_tokens']}")
    print(f"  cached_tokens   : {usage['cached_tokens']}")
    print(f"{'─' * 52}")


# ── --handoff-snapshot ────────────────────────────────────────────────────────
def cmd_handoff_snapshot() -> None:
    src = DERIVED_DIR / "HANDOFF.md"
    if not src.exists():
        print("❌ derived/HANDOFF.md 不存在，请先运行 --sync")
        return
    snap_dir = BASE_DIR / "archive" / "handoffs"
    snap_dir.mkdir(parents=True, exist_ok=True)
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst  = snap_dir / f"HANDOFF_{ts}.md"
    import shutil
    shutil.copy2(str(src), str(dst))
    print(f"✅ 快照已保存：{dst.relative_to(BASE_DIR)}")


# ── exceptions.json 写入 ──────────────────────────────────────────────────────
def _append_exceptions(batch_results: list, batch_id: int) -> int:
    exc = load_json(EXCEPTIONS_FILE, [])
    added = 0
    now_iso = datetime.now(timezone.utc).isoformat()
    for item in batch_results:
        if not item.get("tags_to_add"):
            exc.append({
                "item_id":  item.get("item_id", ""),
                "reason":   item.get("exception_reason", "极度模糊 / 占位图 / 无法归入现有体系"),
                "batch_id": batch_id,
                "ts":       now_iso,
            })
            added += 1
    if added:
        save_json(EXCEPTIONS_FILE, exc)
    return added


# ── 入口 ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Eagle 真实打标脚本")
    parser.add_argument("--prepare",            action="store_true", help="取待处理 items，写 pending.json")
    parser.add_argument("--apply",              action="store_true", help="单张模式：写回 Eagle")
    parser.add_argument("--apply-batch",        nargs="?", const="", default=None, dest="apply_batch",
                        help="批量模式：接通 mimo 打标 + 写回 Eagle（可选 batch_id）")
    parser.add_argument("--checkpoint",         action="store_true", help="手动触发检查点")
    parser.add_argument("--build-review-queue", action="store_true", dest="build_review_queue",
                        help="扫 progress.json，生成 review_queue.json（一次性）")
    parser.add_argument("--review-prepare",     action="store_true", dest="review_prepare",
                        help="取下一批待回溯条目，输出 review_batch_NN.json")
    parser.add_argument("--review-apply",       action="store_true", dest="review_apply",
                        help="读 review_batch_results_NN.json，差集写回 Eagle")
    parser.add_argument("--review-report",      action="store_true", dest="review_report",
                        help="生成 REPORT_review.md 汇总报告")
    parser.add_argument("--limit",   type=int, default=BATCH_SIZE, help="--prepare / --review-prepare 最多取多少条")
    parser.add_argument("--item",    type=str, default="", help="--apply 的 item_id")
    parser.add_argument("--tags",    type=str, default="", help="--apply 的标签（逗号分隔）")
    parser.add_argument("--batch",   type=str, default="", help="--review-apply 指定批次号，如 01")
    parser.add_argument("--confirm", action="store_true", help="--review-apply 跳过交互确认直接执行")
    parser.add_argument("--cleanup",  action="store_true", dest="cleanup",
                        help="主动清理:归档旧版本 .bak + 已完成的 review_* 文件")
    parser.add_argument("--dry-run",  action="store_true", dest="dry_run",
                        help="配合 --cleanup / --triage,仅预览不实际写入")
    parser.add_argument("--build-ge-queue", action="store_true", dest="build_ge_queue",
                        help="扫全部 records，生成 ge_review_queue.json（格-标签分诊输入）")
    parser.add_argument("--triage",      action="store_true", dest="triage",
                        help="对 ge_review_queue.json 做规则分诊，输出 ge_need/skip/uncertain.json")
    parser.add_argument("--ge-prepare",  action="store_true", dest="ge_prepare",
                        help="读 ge_need/uncertain.json，拼 4×4 缩略图网格到 archive/ge_grids/")
    parser.add_argument("--sync",             action="store_true", dest="sync",
                        help="从 config/ 派生 derived/CLAUDE.md / STATE.md / HANDOFF.md")
    parser.add_argument("--handoff-snapshot", action="store_true", dest="handoff_snapshot",
                        help="复制 derived/HANDOFF.md 到 archive/handoffs/HANDOFF_YYYYMMDD_HHMMSS.md")
    parser.add_argument("--test-llm",         type=str, default="", dest="test_llm",
                        help="单张 LLM 测试（item_id），输出 reports/test_llm_<ID>.json，不改 Eagle / progress")
    parser.add_argument("--size",             type=int, default=0, dest="batch_size",
                        help="--apply-batch 本批处理张数（默认 BATCH_SIZE）")
    parser.add_argument("--retry-failed",     type=str, default="", dest="retry_failed",
                        help="重跑指定 batch 中所有失败项（如 024）")
    parser.add_argument("--batch-report",     type=str, default="", dest="batch_report",
                        help="输出指定 batch 的简报到 reports/batch_<id>_report.md")
    args = parser.parse_args()

    if args.prepare:
        cmd_prepare(args.limit)
    elif args.apply:
        if not args.item or not args.tags:
            parser.error("--apply 需要同时提供 --item 和 --tags")
        cmd_apply(args.item, args.tags)
    elif args.apply_batch is not None:
        if args.batch and args.batch.startswith("ge_"):
            cmd_ge_apply_batch(args.batch[3:], dry_run=args.dry_run)
        else:
            cmd_apply_batch(batch_id=args.apply_batch, batch_size=args.batch_size)
    elif args.checkpoint:
        prog = ensure_prog_fields(load_json(PROGRESS_FILE, default_prog()))
        run_checkpoint(prog, force=True)
        save_json(PROGRESS_FILE, prog)
    elif args.build_review_queue:
        cmd_build_review_queue()
    elif args.review_prepare:
        cmd_review_prepare(args.limit)
    elif args.review_apply:
        if not args.batch:
            parser.error("--review-apply 需要同时提供 --batch 批次号，如 --batch 01")
        cmd_review_apply(args.batch, args.confirm)
    elif args.review_report:
        cmd_review_report()
    elif args.cleanup:
        cmd_cleanup(dry_run=args.dry_run)
    elif args.build_ge_queue:
        cmd_build_ge_queue()
    elif args.triage:
        cmd_triage(dry_run=args.dry_run)
    elif args.ge_prepare:
        cmd_ge_prepare()
    elif args.sync:
        cmd_sync()
    elif args.handoff_snapshot:
        cmd_handoff_snapshot()
    elif args.test_llm:
        cmd_test_llm(args.test_llm)
    elif args.retry_failed:
        cmd_retry_failed(args.retry_failed)
    elif args.batch_report:
        cmd_batch_report(args.batch_report)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
