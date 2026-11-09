<!-- AUTO-GENERATED FROM /config/. DO NOT EDIT.
     Last sync: 2026-11-09 21:21:19 from tags.json v2.7.0 -->

# Eagle 素材库打标签项目 — 当前状态


最后同步：2026-11-09 21:21:19　　进度：22700 / 22692 张

---

## 当前进度

- **已处理**：22700 / 22692 张（100.04%）
- **最后 item_id**：`LJ2I7P2BUAD7L`
- **当前批次号**：3328

---

## 词表统计（config/tags.json v2.7.0）

- 标签总数：**382 个 / 23 个前缀**

| 前缀 | 数量 |
|------|------|
| 类- | 17 |
| 题- | 25 |
| 风- | 15 |
| 格- | 24 |
| 版- | 9 |
| 氛- | 14 |
| 光- | 18 |
| 镜- | 18 |
| 构- | 14 |
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
| 代- | 16 |
| 姿- | 8 |
| 服- | 14 |
| 职- | 10 |

---

## 待审建议标签（suggested_tags.json，count≥3）

（无）

所有 suggested 条目（共 43 个）：['氛-动感', '氛-复古', '类-场景设定', '类-角色设定', '格-星空', '题-末世', '格-战争机器', '格-完美音浪', '格-毁灭战士', '格-Project Breach（莉莉丝游戏科幻射击项目）']

---

## exceptions.json

累计 2 条

---

## 下一步待办（DeepSeek 视觉模式）

1. `python tag_real.py --probe-llm`（确认 key/模型/图像输入可用）
2. `python -u run_ai_loop.py --limit 200 --workers 4`（prepare + 线程版写回，跑到 pending 清空）
3. 单独补打某批：`python tag_real.py --prepare --limit 200` → `--apply-batch --threaded`
4. 词表晋升：`python tag_real.py --promote-suggested`（每批结束已自动跑）
5. 每 50 张自动检查点；`--sync` 刷新 derived/

---

## 踩过的坑（简版）

| 坑 | 解决方案 |
|---|---|
| 系统代理劫持 localhost | ProxyHandler({}) 绕过 |
| limit 小时分页截断 | 统一 limit=1000 |
| Eagle API 无总数字段 | limit=25000 探底得 22692 |
| orderBy=-CREATEDATE 排序反了 | 去掉 orderBy |
| btime=0 老素材 | 改用 modificationTime |
