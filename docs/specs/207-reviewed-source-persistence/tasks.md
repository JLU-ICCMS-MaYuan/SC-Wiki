# 实施任务

输入：[规格](spec.md)、[计划](plan.md)、[依据](research.md)、[模型](data-model.md)、[契约](contracts/persistence.md)。

- [x] T001 [US1] 在tests/01_decentralized_uploading/test_reviewed_source_persistence.py建立定位标记、归纳引用和来源缺失失败证明。
- [x] T002 [US1] 实现backend/ingest/reviewed_sources.py并接通backend/api/rag.py及backend/ingest/property_evidence.py的身份持久化。
- [x] T003 [US2] 统一backend/ingest/scientific_evidence.py转接及backend/services/paper_revisions.py、field_review_commit.py的审核后保存。
- [x] T004 [US1] [US2] 验证CaH6隔离完整提交、正式重读、返修及两管理员事务，保留失败与成功证据。
- [x] T005 执行字段/表单/变异与既有回归，更新Overview、validation.md及需求清单，精确提交并回写Issue。

依赖T001→T002→T003→T004→T005，同文件串行。FR-001/SC-001对应T001/T002/T004；FR-002/003对应T002/T003/T004；FR-004对应T003/T004；FR-005/SC-003对应T005。
