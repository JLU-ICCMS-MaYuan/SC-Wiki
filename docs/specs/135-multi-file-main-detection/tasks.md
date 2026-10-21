# 实施任务：多文件正文自动识别与统一解析来源

**输入**：[Spec](spec.md)、[Plan](plan.md)、[Research](research.md)、[数据模型](data-model.md)、[接口](contracts/api.md)

## 基础能力

- [ ] T001 [US1] 在 `tests/01_decentralized_uploading/test_document_roles.py` 先覆盖 La-Sc-H SI 首位、H3S 正文首位、双主文和证据不足。
- [ ] T002 [US1] 在 `backend/ingest/document_roles.py` 实现确定性角色评估与来源信号，保存声明/有效角色。
- [ ] T003 [US1] 在 `backend/ingest/upload_jobs.py` 将评估放在提取后、引文与分段 LLM 前；统一有效角色进入后续流程。

## 歧义与恢复

- [ ] T004 [US2] 在 `backend/ingest/upload_contracts.py`、`backend/ingest/upload_tasks.py` 定义 `needs_role_review` 状态、版本与保留期。
- [ ] T005 [US2] 在 `backend/api/upload_tasks.py` 实现带鉴权、版本和完整角色校验的确认接口并从缓存文本恢复。
- [ ] T006 [US2] 在 `frontend/src/components/MultiFileUploadPanel.tsx` 与任务详情中展示自动纠正/歧义依据和确认控件。

## 来源一致性与验证

- [ ] T007 [US3] 在 `backend/ingest/` 建立共用来源读取器，迁移研究驱动力、关键词、理论子类型、材料家族、引文和核对的有效角色读取。
- [ ] T008 [US3] 在 `tests/01_decentralized_uploading/` 执行任务状态、跨字段来源、角色失效、单文件和结构附件的生产路径回归。
- [ ] T009 更新 `docs/overview/01_Decentralized_Uploading_of_Superconductivity_Data/` 与 `README.md`，记录实际行为并完成 Issue 核对。

## 依赖与覆盖

T001→T002→T003；T004→T005→T006；T007 依赖 T002～T005，T008～T009 在集成后。FR-001～002 对应 T001～T003；FR-003 对应 T004～T006；FR-004～005 对应 T007～T009。
