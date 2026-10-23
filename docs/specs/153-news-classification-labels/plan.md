# 实施计划：快讯自动分类

**Issue**：[#153](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/153)
**日期**：2026-10-22
**Spec**：[spec.md](spec.md)

## 摘要与技术上下文

2026-10-23 扩展：Go 在计数和分页之前应用同一自然周谓词；week/history 为互补集合，旧 API 默认 all。响应含北京时间周一 week、下周一 week_end 和 timezone；前端每栏保存锚点，各自切换历史并重置页码。本周末页或空列表显示“历史更多”，历史模式提供“返回本周”。跨周、跨年、边界秒、未知精度、分页和独立切换均专项验证。业务迁移与发布采用已提交代码，先备份，核对前置加法迁移；数据容器不重建。

Python/SQLAlchemy/RQ/Redis 完成分类写入，MySQL 保存，Go/Gin/GORM 只读，React 19/MUI 7 展示。复用服务器默认 OpenAI 兼容 LLM，分类调用不进入 PDF 队列。pytest、Go test、Vitest 及浏览器验证。面向现有全部资讯，单任务最多三条，优先新内容；不在数据库事务内等待模型。

## 质量门

| 约束 | 落实 | 状态 |
|---|---|---|
| 用户方案 | Spec FR-001 至 FR-007 逐项展开 | 已核对 |
| AGENTS 分支与提交 | mayuan，修改前核对，独立路径暂存 | 执行中 |
| 资讯隔离 | 两张资讯分类表，仅只读材料目录 | 设计已定 |
| 文档 | 原话和原图归档，Issue 关联 | 本地完成，远程链接未发布 |

## 组件及数据流

backend/news/classification.py 负责目录、指纹、校验、分类领取和写回。news_feed_classifications 以 item_id 为主键，news_feed_material_families 保存已有家族引用。采集代码不调用模型；调度器每分钟在采集任务之后追加一个分类批次，沿用 scwiki-news Worker。每批三个候选，先领取并保存尝试计数，调用结束再次锁定并核验 token、内容和目录指纹。任务中断五分钟后可重领，失败间隔一小时，最多三次，输入变化重置预算。批次超时 240 秒。

按 last_seen_at、first_seen_at 倒序扫描，跳过输入及规则未变的已完成项；每分钟补扫可恢复遗漏，历史自然回填。生产部署迁移后启动新进程才启用。原表无新字段，资讯合并/删除用数据库级联删除附属分类。

Go 批量读取本页分类及家族，仅展示 completed 且标题摘要指纹一致的结果。前端响应式测量标签行，超过可用空间显示 +N，抽屉完整展示；增加统一条目高度，保留固定槽位和分页。

## 文档结构

spec.md、approved-plan.md、plan.md、research.md、data-model.md、contracts/feed.md、tasks.md、quickstart.md、checklists/requirements.md 与 assets/。

## 需求到设计与任务映射

| 来源 | 实现与任务 | 验证 |
|---|---|---|
| FR-001/002/003、SC-001、US1 | 分类服务 T002 | 枚举、家族白名单、真实模型 |
| FR-004/005、SC-002、US2 | 任务领取写回/调度 T002/T003 | 更新、合并、恢复、幂等 |
| FR-006、SC-003、US1 | Go/API/React T004 | 跨语言、Vitest、浏览器 |
| FR-007、SC-004 | 迁移/隔离验证/文档 T001/T005 | 哨兵记录、验证报告 |

## 阶段与依赖

T001 数据与规格 → T002 分类 → T003 调度 → T004 接口页面 → T005 验证与文档。单 Feature 无依赖环。

## 必要复杂度

独立处理记录和尝试 token 用于防止并发与超时旧任务覆盖；关联表确保家族来自现有目录。拒绝页面现场 LLM 调用，以免重复付费和页面阻塞。
