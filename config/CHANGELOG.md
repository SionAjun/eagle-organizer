# 词表 / 规则变更日志

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
