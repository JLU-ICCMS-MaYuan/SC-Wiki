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

## US2：本轮解析token记录与显示（2026-11-09）

- [x] T008 [US2] 保存用户“开始”原话及确认，更新#170和本目录设计/数据/接口/检查表，核对FR-007～011与SC-005～008覆盖。
- [x] T009 [US2] 在tests/01_decentralized_uploading/test_upload_token_usage.py及upload-extraction-timing.test.tsx覆盖真实请求用量、缺失、失败、暂停/继续、幂等和重试隔离，先确认新增能力在旧实现下失败。
- [x] T010 [US2] 在backend/rag/token_usage.py与llm.py增加实际请求边界收集；backend/ingest/model_memory.py接入摘要usage_metadata。
- [x] T011 [US2] 在backend/ingest/upload_usage.py、upload_contracts.py、upload_tasks.py和upload_jobs.py集成轮次、请求幂等、状态聚合、公开与既有持久恢复。
- [x] T012 [US2] 在前端任务类型、显示辅助函数、UploadTaskCenter及中英文字典展示总量、输入/输出明细与完整性。
- [x] T013 [US2] 执行原耗时及相关后端/前端回归、构建、实际页面中英文/窄屏验证；必要时执行科学字段/四宿主表单及变异契约。
- [x] T014 [US2] 验证真实模型返回用量→生产收集/存取→页面对照，覆盖摘要与自动谱调用边界、检查点复用及SQLite恢复；保存实际证据和限制。
- [x] T015 [US2] 更新validation.md、需求检查表与已实现Overview，只提交本次验证文件，保持未授权推送及远程链接关闭门。

已查明自动谱backend/spectra/vision.py与原生PDF backend/ingest/native_pdf.py绕过统一JSON入口，T010/T014同时覆盖这两处实际SDK边界；Responses实际用量使用input_tokens/output_tokens。仅补全已确认的本轮自动解析消耗范围，不修改科学输出规则。

US2验证证据：[汇总](assets/token-usage/validation-result.json)、[真实用量](assets/token-usage/live-usage.json)、[浏览器](assets/token-usage/browser-result.json)；后端123、前端22、四宿主表单225项通过，变异12项检出。T015随本次独立提交完成；Issue保留远程文档门，不推送。
