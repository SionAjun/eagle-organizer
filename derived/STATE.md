<!-- AUTO-GENERATED FROM /config/. DO NOT EDIT.
     Last sync: 2026-08-15 13:41:32 from tags.json v2.5.2 -->

# Eagle 素材库打标签项目 — 当前状态


⚠️ exceptions.json 累计 78 条，建议集中处理


> Note: last checkpoint at 21800, current total 21818
最后同步：2026-08-15 13:41:32　　进度：21818 / 20605 张

---

## 当前进度

- **已处理**：21818 / 20605 张（105.89%）
- **最后 item_id**：`MP8IULGWIWFFZ`
- **当前批次号**：3320

---

## 词表统计（config/tags.json v2.5.2）

- 标签总数：**367 个 / 23 个前缀**

| 前缀 | 数量 |
|------|------|
| 类- | 17 |
| 题- | 24 |
| 风- | 13 |
| 格- | 22 |
| 版- | 9 |
| 氛- | 14 |
| 光- | 18 |
| 镜- | 15 |
| 构- | 10 |
| 场- | 16 |
| 角- | 21 |
| 物- | 13 |
| 材- | 24 |
| 色- | 12 |
| 教- | 6 |
| 件- | 37 |
| 载- | 24 |
| 域- | 4 |
| 派- | 23 |
| 代- | 14 |
| 姿- | 7 |
| 服- | 14 |
| 职- | 10 |

---

## 待审建议标签（suggested_tags.json，count≥3）

['风-平涂', '构-俯视', '风-手绘', '镜-全身', '题-科幻', '格-原神', '构-网格', '角-战士', '构-散点', '镜-近景', '构-不对称', '代-中世纪', '题-战斗', '物-现实动物', '镜-半身', '代-现代', '姿-跪伏', '格-哥谭骑士']

所有 suggested 条目（共 57 个）：['氛-动感', '风-平涂', '氛-复古', '类-场景设定', '类-角色设定', '构-俯视', '格-星空', '题-末世', '格-战争机器', '格-完美音浪']

---

## exceptions.json

累计 78 条（建议集中处理）

---

## 下一步待办（agent 视觉模式，mimo API 已停用）

1. `python tag_real.py --prepare --limit 200`
2. `python scripts/make_previews.py <预览目录>`
3. agent 读图，输出结果 JSON（可分片，每片 20 条）
4. `python scripts/validate_agent_tags.py <结果文件>`
5. `python tag_real.py --apply-agent <结果文件>`
6. 每 50 张自动检查点

---

## 踩过的坑（简版）

| 坑 | 解决方案 |
|---|---|
| 系统代理劫持 localhost | ProxyHandler({}) 绕过 |
| limit 小时分页截断 | 统一 limit=1000 |
| Eagle API 无总数字段 | limit=25000 探底得 20605 |
| orderBy=-CREATEDATE 排序反了 | 去掉 orderBy |
| btime=0 老素材 | 改用 modificationTime |
