# 下次启动指引

**第一件事：读 STATE.md，了解当前进度和所有已踩的坑。**

---

## 当前进度（2026-05-01 16:26 更新）

已处理 **400 / 20378** 张（1.96%）

---

## 启动顺序

1. 读 `STATE.md`（全部上下文、踩坑记录）
2. 读 `tags.json`（词表，228 个标签，version 2.2）
3. 读 `progress.json`（已处理 ID 列表，跳过这些）
4. 读 `suggested_tags.json`（待审建议标签，先展示给用户）

---

## 下一步操作（批量模式）

```bash
python tag_real.py --prepare --limit 20
```

一次读取全部 20 张图，输出如下 JSON 写入 batch_results.json：

```json
[
  {"item_id": "xxx", "tags_to_add": ["类-角色设定", "风-写实"], "suggested": ["新概念"]},
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
- progress.json 里已有 400 条记录，--apply-batch 会自动跳过已处理项

---

## 关键记住

- 系统代理劫持 localhost，脚本已用 `ProxyHandler({})` 绕过
- 分页用 `limit=1000`，不传 `orderBy`
- 写回前自动拉旧标签合并，不覆盖手动标签
- 每 50 张自动检查点；也可手动：`python tag_real.py --checkpoint`
- tags.json 在一个批次内只加载一次（_apply_one 复用已加载的 all_valid_tags）
