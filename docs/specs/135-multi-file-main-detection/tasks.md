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

## 2026-10-28 身份一致性修复

- [x] T010 [US4] 在 backend/ingest/document_identity.py、upload_jobs.py、upload_contracts.py 修复可信标题/DOI 提取及最终角色比较，新增固定失败重放及边界回归。
- [x] T011 [US5] 在 backend/api/rag.py、frontend/src/lib/api.ts、UploadTaskEditor.tsx 展示具体冲突并绑定确认令牌，验证真实差异、取消、确认和过期行为。
- [x] T012 [US4] 从原 PDF/SI 首页及已核验文本定向重提标题/DOI，使用真实配置模型并保留输入/输出/来源；通过正式比较及隔离保存重读。
- [x] T013 [US6] 定向备份并重算指定 La–Sc–H consistency，验证草稿/字段结果不变、Redis/MySQL一致及幂等。
- [x] T014 更新 Overview、Spec 验收及 Issue，并按明确路径提交任务差异，不推送。

依赖：T010→T011/T012→T013→T014。不能以本轮通过勾选旧功能的其他未完成项。

本轮证据：[身份一致性验收](identity-consistency-validation.md)。13 项定向后端、2 项前端、真实浏览器及构建通过；真实模型两轮各 1 次，最终元数据与原 PDF/正式处理一致；定向修正及幂等回读完成。旧套件四项失败及修改前基线已单列，未勾选本轮无关的旧验收。
