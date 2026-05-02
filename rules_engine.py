"""
所有 If-Then 业务逻辑。config/rules.json 只放扁平映射，
复杂推导一律在这里用 Python 写。LLM 改 Python 比改嵌套 JSON 健壮。
"""
import json
from pathlib import Path

CONFIG_DIR = Path(__file__).parent / "config"


def _load_rules() -> dict:
    return json.loads((CONFIG_DIR / "rules.json").read_text(encoding="utf-8"))


# ───────── 格- 候选缩窄（R1~R10）─────────
def candidates_for_ge(tags: set) -> list:
    if "题-赛博朋克" in tags:
        return ["格-赛博朋克2077", "格-命运2", "格-控制"]
    if "题-都市幻想" in tags or "题-近未来" in tags:
        return ["格-绝区零", "格-控制", "格-VA-11 HALL-A"]
    if "题-剑与魔法" in tags and ("角-立绘" in tags or "类-角色原画" in tags):
        return ["格-塞尔达王国之泪", "格-魂系"]
    if "题-硬科幻" in tags and ("物-机甲" in tags or "类-道具设定" in tags):
        return ["格-装甲核心6", "格-质量效应", "格-异形:隔离", "格-命运2"]
    if "题-末日废土" in tags:
        return ["格-辐射系列", "格-逃离塔科夫", "格-死亡搁浅"]
    if "氛-诡异" in tags or "氛-恐怖" in tags:
        return ["格-异形:隔离", "格-控制", "格-雨世界"]
    if "题-复古未来" in tags:
        return ["格-辐射系列", "格-极乐迪斯科", "格-VA-11 HALL-A"]
    if "风-日系" in tags:
        return ["格-明日方舟", "格-绝区零"]
    return []


# ───────── 跳过条件（S1~S4）─────────
def should_skip_ge(tags: set) -> bool:
    if any(t.startswith("格-") for t in tags):
        return True
    rules = _load_rules()
    for skip_tag in rules["ge_skip_when_contains"]:
        if skip_tag in tags:
            return True
    return False


# ───────── 排异（U1）─────────
def filter_incompatible(tags: list) -> list:
    rules = _load_rules()
    incompatible = rules["incompatible_prefixes"]
    tag_set = set(tags)
    blocked_prefixes: set = set()
    for trigger, blocked in incompatible.items():
        if trigger in tag_set:
            if trigger in ("类-UI", "类-排版"):
                blocked = [b for b in blocked if b not in ("格-", "版-")]
            blocked_prefixes.update(blocked)
    return [t for t in tags if not any(t.startswith(p) for p in blocked_prefixes)]


# ───────── 排异：从 rules.json 推导被屏蔽前缀（U2，a1 阶段新接入）─────────

# 模块级缓存：避免每次 _apply_one 都读 rules.json
_INCOMPAT_CACHE = None

def _get_incompat() -> dict:
    """读 rules.json/incompatible_prefixes，缓存到模块级变量。
    返回 {主类: [前缀首字, ...]}（前缀已 strip 掉尾部 -）。
    """
    global _INCOMPAT_CACHE
    if _INCOMPAT_CACHE is None:
        rules = _load_rules()
        raw = rules.get("incompatible_prefixes", {})
        _INCOMPAT_CACHE = {
            primary: [p.rstrip("-") for p in prefixes]
            for primary, prefixes in raw.items()
        }
    return _INCOMPAT_CACHE

def get_blocked_prefixes_from_tags(tags_to_add: list) -> list:
    """从已打标签中检测主类，返回应被屏蔽的前缀列表（不含 -，与老函数 API 兼容）。"""
    incompat = _get_incompat()
    blocked = []
    for t in tags_to_add:
        if t in incompat:
            for pfx in incompat[t]:
                if pfx not in blocked:
                    blocked.append(pfx)
    return blocked


# ───────── 词表前缀过滤器（钩子，未接入主流程）─────────
# 设计用途：build_messages 阶段按主类裁剪注入 prompt 的词表，降低 token 开销，提升标签准确度。
# 当前未启用——审计显示词表 294 标签下 cached 命中率 76.6%，单阶段流程经济性更优。
#
# 激活触发条件（任一）：
#   • 词表突破 ~380 标签
#   • cached 命中率掉到 60% 以下
#   • 平均 prompt_tokens 较基线涨 40%+
#   • P2（按词表组合查图）/P3（Obsidian 集成）项目 kickoff
#   • 全自动跑完 20378 张后启动 stage-1 激活专项
#
# 激活时需配套改造：
#   - build_messages 拆 stage1 + stage2
#   - prompts/ 拆 system_stage1.txt + system_stage2.txt
#   - 多线程批处理改两阶段顺序调用
#   - stage-1 主类误判的退化兜底逻辑

def filter_tags_by_primary(primary_class_tag: str, tags_by_prefix: dict) -> dict:
    """按主类排除不适用前缀，返回过滤后的词表（按前缀分组）。"""
    incompat = _get_incompat()
    blocked = set(incompat.get(primary_class_tag, []))
    if not blocked:
        return tags_by_prefix
    return {pfx: lst for pfx, lst in tags_by_prefix.items()
            if pfx.rstrip("-") not in blocked}


# ───────── 已知前缀（从 tags.json 自动派生）─────────
# 取代 tag_real.py 顶部硬编码 KNOWN_PREFIXES。新增前缀只需在 tags.json 加一组，无需改代码。

_KNOWN_PREFIXES_CACHE = None

def get_known_prefixes() -> list:
    """返回 tags.json 里所有前缀（按 dict 出现顺序，不带 - 后缀）。
    第一次调用读文件并缓存，后续直接返回。
    """
    global _KNOWN_PREFIXES_CACHE
    if _KNOWN_PREFIXES_CACHE is None:
        from pathlib import Path
        p = Path(__file__).parent / "config" / "tags.json"
        d = json.loads(p.read_text(encoding="utf-8"))
        _KNOWN_PREFIXES_CACHE = [k.rstrip("-") for k in d.get("tags", {}).keys()]
    return _KNOWN_PREFIXES_CACHE
