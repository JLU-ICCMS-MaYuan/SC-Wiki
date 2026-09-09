# 实施任务

输入：[规格](spec.md)、[计划](plan.md)、[研究](research.md)、[数据模型](data-model.md)、[契约](contracts/paper-metadata.md)。

## 准备与基础

- [x] T001 完成 `docs/specs/99-paper-metadata-row/` 文档门与 Issue 双向关联。
- [x] T002 在 `backend/models.py`、`goserver/models/models.go`、`alembic/versions/20260909_0099_paper_issue_number.py` 增加可空期号并应用当前数据库迁移。

## US1：上传校对（P1）

- [x] T003 [US1] 在 `backend/ingest/upload_jobs.py`、`backend/ingest/extractor.py`、`backend/api/rag.py` 补齐解析归一化及提交，导入导出保留期号。
- [x] T004 [US1] 在 `frontend/src/components/PaperMetadataRow.tsx`、`frontend/src/components/UploadTaskEditor.tsx`、`frontend/src/lib/paperProcessing.ts` 及中英文词典实现共享书目行与期号输入。

## US2：管理员维护（P1）

- [x] T005 [US2] 在 `frontend/src/pages/AdminPaperEditPage.tsx`、`goserver/handlers/admin.go`、`goserver/handlers/papers.go` 补齐共享布局、保存及详情。

## 验证与收尾

- [x] T006 运行前端回归与构建，在当前 MySQL 验证提交/管理员编辑持久化，并将结果写入 `docs/specs/99-paper-metadata-row/validation.md`。
- [x] T007 回写 `docs/overview/01_Decentralized_Uploading_of_Superconductivity_Data/data-structure-and-form-mapping.md` 和 `docs/overview/02_Decentralized_Maintenance_and_Verification/literature-and-record-review.md`，核对 Issue 文档影响并自动提交本次变更。

## 依赖与验收

T001→T002→T003/T004→T005→T006→T007；串行实施。两个故事共同组成最小交付范围。US1 通过草稿保存和提交后读取验收；US2 通过旧论文编辑与重载验收。FR-001/002、SC-001 对应 T004/T005/T006；FR-003/004、SC-002/003 对应 T002/T003/T005/T006；FR-005 对应 T003/T004/T005/T006。
