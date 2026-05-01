# Eagle 打标项目全景诊断报告
生成时间: 2026-04-24  进度快照: 180 / 20378 张（0.88%）

---

## 1. 目录清单

| 文件名 | 大小 | 最后修改 | 用途 |
|--------|------|----------|------|
| tag_real.py | 51 KB | 04-24 02:18 | 主脚本（prepare/apply/checkpoint/review 全流程） |
| progress.json | **102 KB** | 04-24 21:02 | 核心进度文件，含 processed_ids(180) + records(180) |
| review_queue.json | 36 KB | 04-24 16:02 | 回溯修复队列（78条，全部已完成 ✅ 可归档） |
| review_queue.md | **44 KB** | 04-24 01:59 | review_queue 人类可读版（全完成，可归档） |
| tags.json | 6 KB | 04-24 16:07 | 词表 v2.0.2，199标签，13前缀 |
| tags_source.md | 6 KB | 04-23 09:53 | 词表原始设计稿（历史文档，可归档） |
| CHANGELOG.md | 5 KB | 04-24 16:08 | 词表版本迭代记录 |
| STATE.md | 3.4 KB | 04-24 21:02 | 当前状态（每检查点覆盖写） |
| RESUME.md | 1.5 KB | 04-24 21:02 | 下次启动指引（每检查点覆盖写） |
| HANDOFF.md | 2.5 KB | 04-24 21:02 | 检查点追加日志 |
| REPORT.md | 1.5 KB | 04-24 21:02 | 最新运行报告（每检查点覆盖写） |
| REPORT_review.md | 2.1 KB | 04-24 16:02 | 回溯修复汇总报告（一次性，可归档） |
| checkpoint_log.md | 1.3 KB | 04-24 21:02 | 检查点追加日志（含多条重复entry，见§6） |
| suggested_tags.json | 578 B | 04-24 21:02 | 词表外建议标签（3条，均count=1） |
| pending.json | 3 KB | 04-24 18:59 | 最近一批prepare结果（10条，用完即废） |
| batch_results.json | 1.7 KB | 04-24 20:52 | 最近一批视觉决策（10条，用完即废） |
| pending_review.md | 307 B | 04-24 16:07 | count≥3待审标签（当前无内容） |
| vocab_feedback.md | 1 KB | 04-24 02:24 | 词表缺口记录 |
| v2_test_report.md | 2.3 KB | 04-24 01:59 | v2.0词表升级测试报告（历史，可归档） |
| 交接给新对话的Claude.md | 3 KB | 04-23 15:10 | 早期手工交接文档（已被STATE.md/RESUME.md取代，可归档） |
| **tag_real.py.bak.20260423** | 31 KB | 04-23 21:27 | ⚠️ 旧版脚本备份（可归档） |
| **tags.json.bak.v1.1** | 6.7 KB | 04-23 21:27 | ⚠️ 旧版词表备份（可归档） |
| **tags.json.bak.v2.0-pre-calibration** | 8.2 KB | 04-24 01:58 | ⚠️ 旧版词表备份（可归档） |
| **review_batch_01~08.json** | 各8~10 KB | 04-24 | ⚠️ 回溯准备批次（全完成，可归档） |
| **review_batch_results_01~08.json** | 各2~3 KB | 04-24 | ⚠️ 回溯决策批次（全完成，可归档） |

---

## 2. Python 脚本盘点

| 文件 | 行数 | 修改时间 | 用途 | 状态 |
|------|------|----------|------|------|
| tag_real.py | 1187 | 04-24 02:18 | 主脚本，全流程 | **活跃，唯一必要** |
| dry_run.py | 209 | 04-23 02:10 | 验证分页/断点续跑骨架，不打标 | 已完成使命，可归档 |
| mark_for_review.py | 115 | 04-23 21:30 | 扫progress.json生成review_queue.md（只读不写Eagle） | 功能已并入tag_real.py的--build-review-queue，可归档 |
| test_suggested_upgrade.py | 153 | 04-23 15:24 | suggested_tags v1.1格式升级单元测试 | 一次性测试，已完成，可归档 |

**功能重叠判断**：mark_for_review.py 与 tag_real.py --build-review-queue 高度重叠（同样扫records，生成队列）。dry_run.py 和 test_suggested_upgrade.py 均为一次性验证脚本。

---

## 3. JSON 体积与结构

| 文件 | 大小 | 顶层Key | 关键数组/字典大小 |
|------|------|---------|-----------------|
| progress.json | **102 KB** | 12个 | processed_ids: 180条, records: 180条, tag_version_used: 180条 |
| review_queue.json | 36 KB | 5个 | 78条，全部reviewed=true |
| tags.json | 6 KB | 3个 | tags: 13前缀×合计199标签 |
| suggested_tags.json | 578 B | 2个 | suggested: 3条（氛-动感/风-平涂/氛-复古，各count=1） |
| pending.json | 3 KB | 7个 | 10条（最近一批prepare） |
| batch_results.json | 1.7 KB | 3个 | 10条（最近一批结果） |

**progress.json records 详细分析**：
- 条目数：180
- 单条平均字节：273 B
- records 字符总量：49,078
- **预估 token 数：~32,700 tokens（按1 token≈1.5中文字符）**
- 全文件含 processed_ids 列表后估计 **~70,000 tokens**（每次新会话若全量加载则极昂贵）
- 优化建议：新会话只需 `processed_ids` 列表（用于去重），`records` 数组应按需查询而非全量载入

---

## 4. 历史性能数据

### records 时间戳批次耗时（每10张组内首尾时差）

| 批次 | 总耗时 | 均值/张 | 备注 |
|------|--------|---------|------|
| 第1-10张 | 639s | 63.9s | 单张模式，早期调试 |
| 第11-20张 | 604s | 60.4s | 单张模式 |
| 第21-30张 | 303s | 30.3s | 单张模式 |
| 第31-40张 | 164s | 16.4s | 单张模式 |
| 第41-50张 | 333s | 33.3s | 单张模式 |
| 第51-60张 | 58s | 5.8s | 单张模式，提速明显 |
| 第61-70张 | 83s | 8.3s | 单张模式 |
| 第71-80张 | 134s | 13.4s | 单张模式 |
| 第81-90张 | 175s | 17.5s | 单张模式 |
| 第91-100张 | 135s | 13.5s | 单张模式 |
| **第101-180张** | **~0s** | **~0s** | **批量模式**：时间戳仅记录Eagle写回时延，视觉分析时间在JSON生成阶段（不在records里） |

> **注意**：101-180张的0s是records时间戳的误导性读数。批量模式下Claude视觉分析耗时发生在写batch_results.json时，该阶段无时间戳记录。实际每批10张的视觉分析耗时约1-3分钟（会话内估算）。

### checkpoint_log.md 检查点时间间隔

| 检查点 | 时间 | 累计张数 | 间隔 |
|--------|------|---------|------|
| #1（首次） | 04-23 10:23 | 13 | — |
| #1（重触发） | 04-23 10:23 | 13 | 0min（重复） |
| #1（正式） | 04-23 10:42 | 50 | 19min |
| #2 | 04-23 15:43 | 100 | 301min |
| #2（重复×3） | 04-24 02:30~16:07 | 100~110 | 重复触发 |
| #3 | 04-24 18:48 | 150 | — |
| #3（本批） | 04-24 21:02 | 180 | 134min |

> checkpoint_log 有多条重复 #1/#2 entry，系手动触发或会话重启所致，非bug。

---

## 5. Eagle API 调用点盘查

| 函数 | 行号 | 调用 | 用途 |
|------|------|------|------|
| `iter_items` | L173 | eagle_get `/item/list?limit=1000&offset=N` | 分页拉取所有素材列表（每1000条1次） |
| `cmd_prepare` | L226 | eagle_get `/item/info?id=X` | 每张图拉取当前标签（**每张1次**） |
| `_apply_one` | L306 | eagle_get `/item/info?id=X` | apply时再次拉取最新标签（**每张1次**，防并发覆盖） |
| `_apply_one` | L317 | eagle_post `/item/update` | 写回合并后标签（**每张1次**） |
| `cmd_review_prepare` | L845 | eagle_get `/item/info?id=X` | 回溯批次拉取当前标签 |
| `cmd_review_apply` | L941 | eagle_get `/item/info?id=X` | 回溯写回前再拉标签 |
| `cmd_review_apply` | L966 | eagle_post `/item/update` | 回溯写回 |

**每张图API调用统计（主流程）**：
- `--prepare` 阶段：**1次 GET /item/info**（+分摊的分页GET）
- `--apply-batch` 阶段：**1次 GET /item/info + 1次 POST /item/update**
- **全周期合计：2×GET + 1×POST = 3次API calls/张**

**优化机会**：prepare阶段已拉取 `/item/info` 并存入 `pending.json` 的 `existing_tags`，apply阶段重复拉取是为了处理并发修改。若用户不并发操作Eagle，可将 `_apply_one` 的re-fetch改为直接读 `pending_lookup` 的 `existing_tags`，节省1次GET（减少33%API调用）。

---

## 6. 日志文件摘要

| 文件 | 大小 | 行数 | 概括 |
|------|------|------|------|
| checkpoint_log.md | 1.3KB | 10行 | 检查点追加日志，含3条重复entry（#1×2, #2×4），实际有效检查点3个 |
| HANDOFF.md | 2.5KB | 79行 | 每检查点追加的交接记录，含回溯修复完成标记 |
| REPORT.md | 1.5KB | — | 最新运行报告，每检查点覆盖写，当前显示第151-180张数据 |
| REPORT_review.md | 2.1KB | 60行 | 回溯修复汇总（前100张→v2.0.1），已完成，静态文档 |
| CHANGELOG.md | 4.7KB | 116行 | 词表版本迭代记录（v1.0→v2.0.2），是词表决策溯源的唯一依据 |
| pending_review.md | 307B | 13行 | count≥3待审标签列表（当前无实质内容） |
| vocab_feedback.md | 1KB | 15行 | 回溯阶段词表缺口记录，v2.0.2已修复大部分缺口 |
| v2_test_report.md | 2.3KB | 59行 | v2.0词表升级前的对比测试报告，历史文档 |
| tags_source.md | 5.9KB | 141行 | 词表原始设计稿，CHANGELOG.md已覆盖其核心信息 |
| 交接给新对话的Claude.md | 3KB | 100行 | 早期手工编写的交接文档（v1.0时代），STATE.md/RESUME.md已完全取代 |
| review_queue.md | 44KB | 582行 | **最大的单文件**，回溯队列人类可读版，全部78条已完成，可归档 |

**review_warnings.log**：不存在（回溯阶段未产生任何警告 ✅）

---

## 7. 潜在冗余与可清理项

### 建议归档（移入 `archive/` 子目录，不删除）

| 文件 | 大小 | 归档理由 |
|------|------|---------|
| tag_real.py.bak.20260423 | 31KB | 旧版脚本备份，git无法替代时才需要；已超30天价值周期 |
| tags.json.bak.v1.1 | 6.7KB | 旧词表，CHANGELOG.md已记录版本差异 |
| tags.json.bak.v2.0-pre-calibration | 8.2KB | 旧词表，同上 |
| review_batch_01~08.json（8个） | ~70KB合计 | 回溯准备批次，78条全部reviewed，无再用价值 |
| review_batch_results_01~08.json（8个） | ~23KB合计 | 回溯决策批次，同上 |
| review_queue.json | 36KB | 全部reviewed=true，REPORT_review.md已有汇总 |
| review_queue.md | 44KB | **最大冗余**，44KB人类可读版，全完成，可归档 |
| REPORT_review.md | 2.1KB | 回溯汇总报告，静态历史文档 |
| dry_run.py | 9KB | 验证脚本，已完成使命 |
| mark_for_review.py | 5KB | 功能被tag_real.py吸收 |
| test_suggested_upgrade.py | 7.3KB | 一次性单元测试 |
| tags_source.md | 5.9KB | 被CHANGELOG.md覆盖 |
| v2_test_report.md | 2.3KB | 历史测试报告 |
| 交接给新对话的Claude.md | 3KB | 被STATE.md/RESUME.md取代 |

**归档后可释放：约250KB（当前根目录文件总量约360KB）**

### 建议保留但定期刷新

| 文件 | 建议 |
|------|------|
| progress.json | 保留，但考虑将`records`数组在每500张时导出为`records_archive_001-500.json`，主文件只保留最近50条，可将当前102KB降至约20KB |
| pending.json / batch_results.json | 每批用完即可安全覆盖，无需保留历史版本 |
| checkpoint_log.md | 建议清理重复的#1/#2 entry，仅保留有效触发记录 |

---

## 8. 关键优化建议（供外部分析）

1. **progress.json 体积增长问题**：records数组每张+273B，20378张全处理完将达~5.5MB，预估~370万tokens，会话启动时不应全量加载。建议：新会话只加载`processed_ids`列表（约15KB），records按需查询。

2. **apply阶段重复GET**：每张图在prepare已拉一次标签，apply再拉一次，共2次GET。若能接受prepare结果的时效性（通常几分钟内），可直接用`pending.json`里的`existing_tags`，节省1次API。

3. **batch_results.json无历史保留**：当前每批覆盖写，若Claude中途断线，本批视觉分析结果丢失需重做。建议按批次编号保存（`batch_results_007.json`），与review_batch模式对齐。

4. **suggested_tags均count=1**：3条建议标签（氛-动感/风-平涂/氛-复古）全为count=1，尚无需审核。建议在处理至第300张时集中审核一次。
