# 实施计划

**Issue**：[#147](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/147) · **日期**：2026-10-21 · [规格](spec.md)

## 摘要与技术上下文

基于现有Python/FastAPI、SQLAlchemy/MySQL、Redis/RQ和TypeScript/React实现。复用核对表、草稿存储与队列；字段投影负责身份和值，审核策略负责复用与归属，接口负责权限与并发，界面只渲染结果。Go管理员入口继续委托同一后台门禁。单元测试pytest/Vitest，集成使用MySQL回滚与浏览器隔离草稿。

## 质量门

| 约束 | 实施方式 | 状态 |
|---|---|---|
| 用户最终方案 | spec原话、FR/SC、任务覆盖 | 已核对 |
| AGENTS分支与提交 | mayuan，逐次编辑前检查，仅提交任务文件 | 持续检查 |
| 保护真实数据 | 隔离草稿、回滚测试，不自动批准 | 持续检查 |
| 远程文档链接 | 未推送，Issue标明本地路径 | 待推送授权，不阻断本地实现 |

## 结构与组件

- backend/ingest/property_field_review.py、scientific_evidence.py：独立字段、版本、当前结果与字段历史。
- backend/ingest/field_review.py：统一审核选择、复用、错误归属与提交策略。
- backend/api/evidence.py：摘要、字段保存/说明/历史、任务与门禁接口。
- backend/ingest/property_evidence.py、upload_jobs.py：解析收拢、任务处理和逐字段模型结果。
- backend/api/rag.py、backend/services/paper_revisions.py、goserver/handlers/paper_evidence.go：三种提交路径。
- frontend/src/components/EvidenceWorkflow.tsx、EvidenceFieldMarkers.tsx、UploadTaskEditor.tsx及共用表单：局部保存与独立展示。

## 数据与实现顺序

首先统一字段投影和复用判定，再实现保存/摘要接口与队列，再接入界面和三种提交路径。草稿允许原始输入，正式数据仅在版本审核通过后的事务中应用。历史恢复只在首次构建字段清单/明确迁移时执行，不进入正常保存。字段版本不包含模型名、非语义代码版本或父记录整体摘要。

## 需求到设计与验证

| 来源 | 设计与事实来源 | 任务 | 验证 |
|---|---|---|---|
| FR-001 / SC-001 | 解析任务、去重队列 | T004 | 解析与页面打开调用计数 |
| FR-002 / SC-001,005 / US1 | 稀疏草稿保存、编辑标记 | T003,T006 | 无改零请求、中间文本、P95 |
| FR-003,004 / SC-002 / US2 | 字段投影、摘要/字段历史 | T002,T005 | 独立状态与来源 |
| FR-005,006,007 / SC-003 / US3 | field_review、提交选择 | T002,T004,T007 | 恢复原值、压力归属、部分复用 |
| FR-008,009,010 / SC-004 | 版本锁、结果写入、兼容门禁 | T004,T007,T008 | 故障、并发、绕过测试 |

## 性能与复杂度

447项草稿局部保存P95目标≤1秒，不含模型和传输。禁止保存时加载PDF、全部历史或重建科学快照。字段版本及并发检查是保证不误提交的必要复杂度；不增加每次编辑时的科学检查。
