# 实施任务

输入：[Spec](spec.md)、[Plan](plan.md)、[Research](research.md)、[数据模型](data-model.md)、[契约](contracts/field-candidate.md)。

- [x] T001 创建 Issue #169，归档 docs/specs/169-field-ai-candidates/ 需求与图片。
- [x] T002 [US1] tests/01_decentralized_uploading/test_field_candidates.py 验证提交复用和调用计数，必要时收紧 backend/ingest/property_evidence.py。
- [x] T003 [US2] backend/ingest/field_candidates.py、scientific_evidence.py 保存独立候选并保护人工决定。
- [x] T004 [US2] frontend/src/components/FieldAICandidate.tsx、EvidenceWorkflow.tsx、UploadTaskEditor.tsx 实现侧栏候选与顶部清理，并新增组件测试。
- [x] T005 [US3] backend/api/evidence.py、field_candidates.py 实现准备与确认；UploadTaskEditor.tsx、AdminPaperEditPage.tsx 接入保存器，验证 MySQL 持久化。
- [x] T006 在 docs/specs/169-field-ai-candidates/validation.md 记录定向测试、浏览器、构建与边界，更新 Overview，完成本次任务的提交准备。

依赖 T001→T002／T003→T004／T005→T006，同文件串行。三个 P1 故事共同形成 MVP。
FR-001→T002；FR-002、008→T003；FR-003、006→T004；FR-004、005、007→T005；SC-001—004→T006 验证汇总。
