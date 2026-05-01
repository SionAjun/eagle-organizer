<!-- AUTO-GENERATED FROM /config/. DO NOT EDIT.
     Last sync: 2026-05-01 23:18:27 from tags.json v2.4 -->

# Eagle 素材库打标签项目 — 当前状态



> Note: last checkpoint at 950, current total 960
最后同步：2026-05-01 23:18:27　　进度：960 / 20378 张

---

## 当前进度

- **已处理**：960 / 20378 张（4.71%）
- **最后 item_id**：`MM9B9UBR4OCIO`
- **当前批次号**：52

---

## 词表统计（config/tags.json v2.4）

- 标签总数：**317 个 / 19 个前缀**

| 前缀 | 数量 |
|------|------|
| 类- | 17 |
| 题- | 25 |
| 风- | 13 |
| 格- | 22 |
| 版- | 9 |
| 氛- | 14 |
| 光- | 18 |
| 镜- | 15 |
| 构- | 10 |
| 场- | 16 |
| 角- | 18 |
| 物- | 15 |
| 材- | 24 |
| 色- | 12 |
| 教- | 6 |
| 件- | 32 |
| 载- | 24 |
| 域- | 4 |
| 派- | 23 |

---

## 待审建议标签（suggested_tags.json，count≥3）

['风-手绘', '镜-全身', '格-原神']

所有 suggested 条目（共 20 个）：['氛-动感', '风-平涂', '氛-复古', '类-场景设定', '类-角色设定', '构-俯视', '格-星空', '题-末世', '格-战争机器', '格-完美音浪']

---

## exceptions.json

累计 1 条

---

## 下一步待办

1. `python tag_real.py --prepare --limit 20`
2. 读全部图，输出 JSON 写入 batch_results_NNN.json
3. `python tag_real.py --apply-batch`
4. 每 50 张自动检查点

---

## 踩过的坑（简版）

| 坑 | 解决方案 |
|---|---|
| 系统代理劫持 localhost | ProxyHandler({}) 绕过 |
| limit 小时分页截断 | 统一 limit=1000 |
| Eagle API 无总数字段 | limit=25000 探底得 20378 |
| orderBy=-CREATEDATE 排序反了 | 去掉 orderBy |
| btime=0 老素材 | 改用 modificationTime |
