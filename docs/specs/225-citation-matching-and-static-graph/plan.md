# 实施计划

[规格](spec.md)；[Issue #225](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/225)。

## 摘要与技术上下文

Python/SQLAlchemy负责匹配、LLM2及持久化，Go直接查询公开图，React/MUI/vis-network承接展示。使用标准库候选索引，不新增模型运行依赖。

## 质量门

只核对真实原引文与给定候选；读取不调用模型；不改#203标准键和摘要；保留#174/#220/#221及#224。迁移只先隔离验证，业务环境执行不默认为已授权。

## 源代码与职责

backend/services/citation_matching.py负责规范化、候选、模型、缓存和快照；citation_graph.py负责原解析及正式提交/审核。backend/models.py与alembic/versions/20261106_0225_citation_matching.py增加缓存、决定依据、快照及llm2方法。upload_jobs.py只加阶段钩子，api/upload_tasks.py只加鉴权读取。CitationMatchingPage.tsx提供三列页，UploadParsingDetail.tsx和LazyRoutes.tsx提供入口。citationGraphLayout.ts与KnowledgeGraphPage.tsx管理内存坐标；Go KGOverview单独加标题过滤。

## 需求到设计与验证映射

| 来源 | 设计与事实来源 | 任务 | 证据 |
|---|---|---|---|
| FR-001/002、SC-001/002 | 原引文、候选、LLM2决定 | T002/T003 | 真实正负例、协议及模型回执 |
| FR-003/004/006、SC-002/003 | 输入/候选签名、缓存、快照、正式依据 | T003/T004 | 失效/持久重读/审核/读取零调用 |
| FR-005、SC-004 | 上传所有者权限、三列只读页 | T005 | API与浏览器 |
| FR-007/008、SC-004 | 概览SQL、稳定坐标 | T006 | Go与浏览器拖拽/刷新 |
| FR-009、SC-005 | 表单原契约、共享源码基线 | T001/T007 | 合同/变异、隔离迁移、提交核验 |

## 阶段与依赖

准备→失败回归→匹配/存储→主链路→结果页/图谱→验证收尾。共享文件串行，不启用子代理。

## 必要复杂度

缓存独立于工作稿，支持暂停复用而不覆盖人工编辑；服务器持有快照、正式归档快照与公开边分开以保留审核边界。候选绑定书目身份，源绑定当前引文版本与原文签名；读取仅检查相关依据。拒绝每次GET调用模型、把LLM决定冒充manual、随机坐标或全图重排。
