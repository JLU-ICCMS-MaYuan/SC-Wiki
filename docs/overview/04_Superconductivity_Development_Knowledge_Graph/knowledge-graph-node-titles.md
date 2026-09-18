# 知识图谱节点标题

## 功能说明

为知识图谱的论文节点生成和展示专用短标题，概括论文核心贡献；节点详情保留完整原标题。

## 当前行为

- MySQL `papers.knowledge_graph_title` 是可空的 `VARCHAR(200)` 字段，独立于原标题 `title`。
- 上传解析的 `SUMMARY_SYSTEM_PROMPT` 要求用 10–15 个英文词概括核心发现和材料体系，避免系列编号和冗长修饰。字段与其他论文叙述字段统一按英文生成，内容不随界面语言切换；缺少原文依据时允许为空。
- 管理员和超级管理员可在论文编辑页修改“知识图谱标题”。字段随论文信息保存，Go 管理员更新与普通论文 PATCH 的字段白名单均包含 `knowledge_graph_title`，实际写入仍受各接口权限约束。
- 引用图概览、搜索和邻居 API 直接读取 MySQL。`nodes[].label` 优先取非空的 `knowledge_graph_title`；值为 `NULL` 或空字符串时回退到 `title`，同时返回完整原标题。
- `/knowledge` 使用上述 API；图中标签超过 42 个字符时截断，选中节点后可查看原标题。公开节点仍须符合当前版本已审核通过的条件。

短标题中对论文贡献的概括不等于图谱里程碑标记；`origin`（源头）和 `breakthrough`（突破）仍由管理员单独维护。

## 工作流程

上传解析先把短标题放入论文草稿，提交时保存到 `papers.knowledge_graph_title`。管理员可以在论文编辑页修订。对当前已审核论文，后续引用图查询直接读取保存后的值，不依赖 Neo4j 同步；缺失短标题的历史论文继续显示原标题。

## 约束

- 10–15 个英文词是生成提示词要求，当前没有专门的词数校验或自动质量评分，不能据此保证每次输出合规。
- 生成质量依赖模型和论文原文，需要人工核对；未提供历史论文批量生成工具。
- 重新发布只同步已有字段，不会为缺失标题重新调用 AI。历史论文可通过管理员编辑页补充。
- 遗留 `/api/knowledge-graph-live` 仍读取 Neo4j 的 `title`，不采用短标题优先规则；它不是当前 `/knowledge` 页面的查询入口。

## 代码与测试

- 数据库迁移：`alembic/versions/20260831_175226_add_knowledge_graph_title.py`
- 模型定义：`backend/models.py` `Paper.knowledge_graph_title`
- AI 生成：`backend/ingest/upload_jobs.py` `SUMMARY_SYSTEM_PROMPT`
- 保存与发布：`backend/api/rag.py`
- 展示 API：`goserver/handlers/knowledge_graph.go` 的 `/overview`、`/papers/{id}/neighbors`、`/search`；`/stats` 只返回节点和边的计数。
- 编辑入口与保存白名单：`frontend/src/pages/AdminPaperEditPage.tsx`、`goserver/handlers/admin.go`、`goserver/handlers/papers.go`
- 前端页面：`frontend/src/pages/KnowledgeGraphPage.tsx`
- 字段保存与编辑测试：`goserver/handlers/papers_test.go`、`tests/02_identity_governance/admin-narrative-edit.test.tsx`

## 相关变更记录

- [Issue #70：知识图谱节点专用标题](../../specs/70-knowledge-graph-title/spec.md)
- [Feature #74：全站中英文界面与英文叙述字段](../../specs/74-site-wide-i18n/spec.md)
- [Feature #81：基于 MySQL 的引用图谱](../../specs/81-citation-graph/spec.md)

## 已知问题

- [Issue #70](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/70) 中标题可用率、长度合规及性能要求尚缺可核验的验收记录；字段生成、保存和展示已实现不等于这些质量指标已达标。
- 同一材料体系多篇论文可能生成相似标题，当前没有标题唯一性约束。
