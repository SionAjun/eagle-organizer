\# Eagle 素材库整理项目 - 新对话交接



\## 我是谁、在做什么

\- 我是游戏美术/概念设计方向的用户

\- 我有一个 Eagle 素材库，共 20,378 张素材（D:\\杂项\\素材.library）

\- 我在用 Claude Code 给这些素材按词表批量打标签

\- 工作目录：C:/GAME 2333/game/Claud cod/eagle-organizer



\## 已完成的事

1\. Eagle API 已跑通（http://localhost:41595）

2\. dry\_run.py 验证过分页（limit=1000,不用orderBy,依赖默认排序,用modificationTime倒序）

3\. tags.json 词表已生成，13 个前缀:类/题/风/氛/光/镜/场/角/兽/物/材/色/教,约 300 个标签,version 1.0

4\. tag\_real.py 真实打标脚本已跑通,--prepare/--apply 分步模式,Claude Code 用 Read 工具看图选标签

5\. 已打标 23 张,质量非常高(如航天FPC产品图打出:类-道具设定+题-硬科幻+风-写实+光-柔光+镜-俯视+色-暖色主导)

6\. Eagle 更新接口已确认:POST /api/item/update, body {"id":"...", "tags":\[...]} 覆盖式写入,需先合并旧标签

7\. 永久授权已配置(.claude/settings.json 里 additionalDirectories + allow),不再每张弹框



\## 已踩过的坑(新 Claude Code 不要再踩)

\- Eagle API 小 limit 分页在 450 条位置会静默截断 → 用 limit=1000+

\- orderBy=-CREATEDATE 排序方向反了,依赖 Eagle 默认排序(按添加时间倒序)

\- 部分老素材 modificationTime=1970-01-01,标记\[时间缺失]但正常处理

\- 系统代理 127.0.0.1:7892 劫持 localhost,Python 脚本要 ProxyHandler({}) 绕过

\- Eagle 每个素材在独立 .info 子文件夹,权限要用 additionalDirectories 永久授权整个库目录



\## 待完成的机制(上次会话上下文撑爆中断)

1\. 每 50 张自动触发检查点(更新 STATE.md/RESUME.md/checkpoint\_log.md)

2\. suggested\_tags.json 升级为聚合结构:{"标签名":{"count":N,"example\_items":\[...]}}

3\. 检查点时扫描 count>=3 的 suggested 推送审核清单,用户审完批量更新 tags.json 升版本



\## 工作规则

\- 词表严格从 tags.json 选,绝不自由发挥

\- 词表外概念走 suggested 聚合,不自动加词表

\- 每 50 张检查点,每 100 张审一次 suggested

\- 看图时用 Read 工具读本地路径

\- 优先新素材、跳过 24 小时保护期内的、跳过已处理的



\## 项目里的关键文件

\- tag\_real.py:主打标脚本

\- dry\_run.py:已废弃的验证脚本(别动)

\- tags.json:主词表 v1.0

\- tags\_source.md:词表原始 markdown 源(万一 tags.json 丢了可重建)

\- progress.json:已处理 item\_id 列表 + 本次进度元数据

\- suggested\_tags.json:待审核的词表外建议

\- STATE.md:完整项目状态

\- RESUME.md:新会话入口指引

\- checkpoint\_log.md:每 50 张的检查点流水

\- logs/:运行日志



\## 我现在对你(新对话 Claude)的要求

请先读 STATE.md 和 RESUME.md,用一段话汇报当前进度,然后等我指示,不要自作主张。

