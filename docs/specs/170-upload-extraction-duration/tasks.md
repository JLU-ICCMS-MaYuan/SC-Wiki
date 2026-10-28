# 实施任务
输入：[Spec](spec.md)、[Plan](plan.md)、[Research](research.md)、[数据模型](data-model.md)、[接口](contracts/timing.md)。

## 准备
- [x] T001 核对 docs/specs/170-upload-extraction-duration/spec.md 与用户已确认草案，保存原图和需求检查表。

## US1：显示本轮解析用时（P1，MVP）
- [x] T002 [US1] 在 tests/01_decentralized_uploading/test_upload_extraction_timing.py 验证运行区间、暂停/终态/重试、存取与公开字段。
- [x] T003 [US1] 在 tests/01_decentralized_uploading/upload-extraction-timing.test.tsx 验证实时、刷新、终态、迟到响应及历史数据。
- [x] T004 [US1] 修改 backend/ingest/upload_contracts.py、backend/ingest/upload_tasks.py 记录并公开计时。
- [x] T005 [US1] 修改 frontend/src/lib/paperProcessing.ts、frontend/src/lib/uploadExtractionTiming.ts、frontend/src/components/UploadTaskCenter.tsx、frontend/src/i18n/zh/upload.ts、frontend/src/i18n/en/upload.ts，实现列表显示与轮询。

## 验证与收尾
- [x] T006 在 tests/01_decentralized_uploading/upload-extraction-timing-browser.mjs 验证真实页面中英文、窄屏、交互与时间变化；执行构建并写 validation.md。
- [x] T007 按实现更新 docs/overview/01_Decentralized_Uploading_of_Superconductivity_Data/pdf-parsing-pipeline.md，核对范围；验证后单独提交本次文件。

## 依赖与覆盖
T001→T002/T003→T004/T005→T006→T007；测试分别验证前后端，实际执行串行，避免共享工作区冲突。
FR-001/006及SC-004对应T003/T005/T006；FR-002/003/005及SC-001/003对应T002/T004/T006；FR-004及SC-002对应T002～T006。
US1独立验收为新任务开始计时、暂停恢复、终态冻结、刷新恢复和重试独立。无额外增量计划；Issue协作状态以GitHub为准。
