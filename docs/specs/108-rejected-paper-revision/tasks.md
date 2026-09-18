# 实施任务

**输入**：[spec.md](spec.md)、[plan.md](plan.md)、[research.md](research.md)、[data-model.md](data-model.md)、[契约](contracts/revision.md)

## 准备与基础

- [x] T001 检查文档一致性与需求覆盖，完成 docs/specs/108-rejected-paper-revision/checklists/requirements.md。
- [x] T002 [US1] 在 backend/tests/test_paper_revisions.py 建立权限、持久化、基线冲突及历史数据恢复测试。
- [x] T003 [US1] 在 backend/models.py、alembic/versions/20260918_0108_paper_revision_drafts.py、backend/services/paper_revisions.py、backend/api/paper_revisions.py 实现持久草稿与来源转换。

## 提交与核对

- [x] T004 [US2] 在 backend/tests/test_paper_revisions.py 添加核对、真实升版、回滚、重试与再次返修测试。
- [x] T005 [US2] 在 backend/ingest/property_evidence.py、backend/api/evidence.py、backend/services/paper_revisions.py 接入 revision 核对与单事务提交，保留审核分类恢复。

## 用户界面

- [x] T006 [US1] 在 tests/01_decentralized_uploading/paper-revision.test.tsx 及 goserver/handlers/paper_access_test.go 添加入口、权限与交互测试。
- [x] T007 [US1] [US2] 在 frontend/src/pages/PaperRevisionPage.tsx、frontend/src/components/UploadTaskEditor.tsx、frontend/src/components/MyPapersList.tsx、frontend/src/components/PaperEditView.tsx、frontend/src/LazyRoutes.tsx 及中英文字典实现入口与共享返修表单；goserver/handlers/papers.go 输出能力并限制旧 PATCH。

## 验收与文档

- [x] T008 执行隔离 Python/Go/前端测试和构建，将结果写入 docs/specs/108-rejected-paper-revision/validation.md。
- [x] T009 按已验证行为更新两个相关 Overview 和 README.md，核对 Issue/Spec 双向关联，仅提交本次变更。

## 依赖与覆盖

T001 → T002/T003 → T004/T005 → T006/T007 → T008/T009；全部在当前分支串行完成，共享文件不并行写入。
FR-001/003/007/009 与 SC-001/002 对应 T002/T003；FR-004/005/006/008 与 SC-003/004 对应 T004/T005；FR-002/010 对应 T006/T007；完整用户旅程由 T008 验证，文档由 T009 收敛。
MVP 包含 US1 与 US2，不能只交付可编辑按钮。

## 验证依据

任务完成依据见 [validation.md](validation.md)。返修专项包含真实 MySQL 与跨 Go 审核；共享文件按改动片段分离，并在仅包含本功能的独立副本上通过验证。
