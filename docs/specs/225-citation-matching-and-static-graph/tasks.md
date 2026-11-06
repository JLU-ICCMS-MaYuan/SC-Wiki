# 实施任务

输入：[规格](spec.md)、[计划](plan.md)、[研究](research.md)、[数据](data-model.md)、[接口](contracts/citation-matching.md)。

## 准备与基础

- [x] T001 保存完整原话、两张原图、共享基线和真实模型对照至本目录assets与隔离准备目录。
- [x] T002 [US1] backend/tests/test_citation_matching.py先复现排版遗漏、模型错连/漏答和缓存故障。
- [x] T003 [US1] backend/services/citation_matching.py、backend/models.py、alembic/versions/20261106_0225_citation_matching.py实现匹配、证据和持久缓存。
- [x] T004 [US1] backend/ingest/upload_jobs.py和backend/services/citation_graph.py接入汇总、保存、提交、批准。

## 展示

- [x] T005 [US2] backend/api/upload_tasks.py、CitationMatchingPage.tsx、UploadParsingDetail.tsx、LazyRoutes.tsx接入权限和新标签页。
- [x] T006 [US3] citationGraphLayout.ts、KnowledgeGraphPage.tsx及goserver/handlers/knowledge_graph.go实现稳定布局及概览筛选。

## 收尾

- [x] T007 完成真实来源隔离重跑、模型/缓存/持久重读、权限/浏览器、Go/Python、字段/表单合同/变异与构建；更新Overview/README及旧规则引用；仅提交测试过的本次字节。

## 依赖、MVP及覆盖

T001→T002→T003→T004→T005/T006→T007；同文件串行。US1+US2为MVP，US3本批交付。FR-001/002映射T002/T003；FR-003/004/006映射T003/T004；FR-005映射T005；FR-007/008映射T006；FR-009和SC-001至005映射T007。Issue是协作状态唯一入口。

## 本地完成依据

T002/T003：匹配回归及真实LLM2回执；T004：隔离MySQL工作稿、提交／批准、新会话重读；T005/T006：真实全栈浏览器与Go专项；T007：字段锁定、210项四宿主表单、12项变异、构建与隔离清理，详见[validation.md](validation.md)。本次提交仅包含已验证投影字节。远程链接与业务升级未执行，不作为任务已验收的隐含事实。
