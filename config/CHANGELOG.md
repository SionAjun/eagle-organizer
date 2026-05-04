# 词表 / 规则变更日志

## 2026-05-04 — v2.5.1: 前缀重叠裁决

- 删除 4 标签: 角-战士/角-平民/题-战斗/物-飞船（前缀重叠裁决，职-/载- 为语义更准确的前缀）
- 新增 3 条同义改写: 角-战士→职-战士, 角-平民→职-平民, 物-飞船→载-飞船
- 题-战斗 直接删除（脏数据清理，不加同义）
- prompts/dimensions.txt 追加 5 组重名标签维度区分说明（机甲/战术装备/维多利亚/太空/战斗）
- 回填命中: data/batches 21 命中 / progress.json 7 命中 / Eagle 库 22 命中
- 合计 362 标签，23 个前缀

## 2026-05-04 — v2.5: 词表扩展（代-/姿-/服-/职-）

- 新增「代-」前缀(14 个): 文化时空背景（中式/新中式/日式/和风/欧式古典/北欧/地中海/阿拉伯/印度/非洲部落/维多利亚/巴洛克/洛可可/哥特）
- 新增「姿-」前缀(7 个): 人物姿态（站立/坐姿/蹲伏/躺卧/奔跑/战斗/飞行）
- 新增「服-」前缀(14 个): 服装形制（机甲/战术装备/动力装甲/便装/西装/制服/学生装/长袍/铠甲/皮甲/法袍/民族服饰/华丽/破损）
- 新增「职-」前缀(10 个): 人物身份（战士/法师/刺客/射手/工匠/学者/商人/平民/士兵/领袖）
- 角- 前缀追加 5 个: 儿童/青年/中年/老人/非人
- 删除 物-摩托（并入 载-摩托，同义改写规则）
- rules.json v2.3.0: 新增 synonyms 字段（物-摩托 → 载-摩托）
- 新增 config/prompts/dimensions.txt（维度组合说明，挂载至 build_messages）
- 回填: 18 个 batch 文件、58 张图片 batch 替换 + 83 张 Eagle API 同步
- 合计 366 标签，23 个前缀

- 2026-04-30  tags.json v2.2：格-喷射战士 从 suggested 升入词表（count=3），228 标签
- 2026-04-30  rules.json v2.2.0：新增格-命名规范（尽量中文译名）；suggested_tags 清理（删除 Concord，Starfield→星空，Splatoon→喷射战士，Hi-Fi Rush→完美音浪，DOOM→毁灭战士，Blade Runner→银翼杀手）
- 2026-04-30  检查点压缩机制：checkpoint_log/HANDOFF 超过 10 条自动压缩旧记录至 archive/，保留最近 10 条（workflow.json compress_after=10）
- 2026-04-26  rules.json v2.1.1：阶段 2 重构起点，rules 仅放扁平映射
- 2026-04-25  tags.json v2.1：新增格-/版- 前缀，227 标签 / 15 前缀
- 2026-04-24  tags.json v2.0.2：色暖色主导/冷色主导补回
- 2026-04-24  tags.json v2.0.1：13 前缀全量对账
- 2026-04-23  tags.json v2.0：兽前缀废除，5 个迁入角

## 2026-05-03 — a1-1: incompatible_prefixes 真相迁移

- 以 tag_real.py 顶部 INCOMPATIBLE_PREFIXES 为真相，重写 config/rules.json 的 incompatible_prefixes 字段
- 此前两处不一致：rules.json 是早期设想（4 前缀 / 3 类目），tag_real.py 是实际生效版本（8 前缀 / 5 类目，已经过 580 张图实证）
- 砍掉 rules.json 里孤立的 "类-实景参考" 规则（从未生效过，且与用户实际打标习惯冲突——实景参考图需要保留光/镜/氛/场标签）
- 本次仅同步配置文件，不改动运行时逻辑；接通由 a1-2 完成

## 2026-05-03 — a3: 删除未接入的 normalize_synonyms 死代码

- 删除 rules_engine.py 的 normalize_synonyms 函数（定义存在但主流程从未调用）
- 删除 config/rules.json 的 ge_synonyms 字段
- 决策依据：实证检查 suggested_tags.json 后发现 0 条匹配场景——LLM 没有同义词归一需求，词表外标签都是真实词表缺失（应入表评审）而非简写
- 真出现简写需求时，5 行代码可重写；保留死代码反而是契约谎言
- 未受影响：filter_tags_by_primary 钩子保留（B+ 方案，未来 stage-1 激活时使用）
