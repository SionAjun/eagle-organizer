<!-- AUTO-GENERATED FROM /config/. DO NOT EDIT.
     Last sync: 2026-05-04 18:00:00 from tags.json v2.5 -->

# Eagle 素材库打标签项目 — 当前状态



> Note: last checkpoint at 950, current total 970
最后同步：2026-05-04 18:00:00　　进度：970 / 20378 张

---

## 当前进度

- **已处理**：970 / 20378 张（4.76%）
- **最后 item_id**：`MON605ZTVACYZ`
- **当前批次号**：55

---

## 词表统计（config/tags.json v2.5）

- 标签总数：**366 个 / 23 个前缀**

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
| 角- | 23 |
| 物- | 14 |
| 材- | 24 |
| 色- | 12 |
| 教- | 6 |
| 件- | 32 |
| 载- | 24 |
| 域- | 4 |
| 派- | 23 |
| 代- | 14 |
| 姿- | 7 |
| 服- | 14 |
| 职- | 10 |

---

## 待审建议标签（suggested_tags.json，count≥3）

['风-手绘', '镜-全身', '格-原神']

所有 suggested 条目（共 19 个）：['氛-动感', '风-平涂', '氛-复古', '类-场景设定', '类-角色设定', '构-俯视', '格-星空', '题-末世', '格-战争机器', '格-完美音浪']

---

## exceptions.json

累计 1 条

---

## 人工基线系统

- **baseline_001**：focus=派-，好1/部分7/坏2（index.jsonl 累计 20 条）
- **baseline_002**：focus=构-，好8/部分2/坏0
- **insights.md**：6 大类洞察（A-F），主线 1 评审核心输入
- 模板 v2：无"整体"行，overall 自动推导

---

## 下一步待办

1. 主线 1：评审 insights.md 中的系统性问题，决策词表 v2.5 演进
2. `python tag_real.py --prepare --limit 20`
3. 读全部图，输出 JSON 写入 batch_results_NNN.json
4. `python tag_real.py --apply-batch`
5. 每 50 张自动检查点

---

## 踩过的坑（简版）

| 坑 | 解决方案 |
|---|---|
| 系统代理劫持 localhost | ProxyHandler({}) 绕过 |
| limit 小时分页截断 | 统一 limit=1000 |
| Eagle API 无总数字段 | limit=25000 探底得 20378 |
| orderBy=-CREATEDATE 排序反了 | 去掉 orderBy |
| btime=0 老素材 | 改用 modificationTime |
