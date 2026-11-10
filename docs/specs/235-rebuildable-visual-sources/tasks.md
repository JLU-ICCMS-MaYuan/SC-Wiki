# 技术任务：以PDF与版本化定位重建裁剪并供快照及RAG复用

输入：[spec.md](spec.md)、[plan.md](plan.md)、[research.md](research.md)、[data-model.md](data-model.md)、[接口契约](contracts/tool-and-source.md)。协作状态以[Issue #235](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/235)为准。

**当前仅文档交付，以下实施和运行验证均未在本轮执行，不因存在试改而勾选。**

## 阶段1：准备

- [ ] T001 在本目录`spec.md`与`../232-complete-pdf-regions/conversation.md`对照完整原话、模型/存储替代结论和已有依赖，固定来源及验收样本。

## 阶段2：US1——采用结果方便复用（P1）

独立验收：缓存命中与清理后重建均保持同一区域，不重新调用模型找坐标。 覆盖FR-001、FR-002、FR-003、FR-004。

- [ ] T002 [US1] 在`backend/tests/test_pdf_regions.py`新增能覆盖本故事真实边界的固定反例/交互测试，先证明已知故障可失败。
- [ ] T003 [US1] 在`backend/ingest/pdf_regions.py`及本目录`contracts/tool-and-source.md`约束下实现本故事，保持来源、原主模型和科学字段所有权。
- [ ] T004 [US1] 接入`backend/ingest/document_storage.py`及本故事涉及的现有宿主，运行新反例和来源保存重读/权限/恢复集成，保留前后证据。

## 阶段3：US2——快照轻量且历史准确（P1）

独立验收：快照无PNG复制，返修后旧快照与原件仍一致。 覆盖FR-005、FR-006、FR-007、FR-010、FR-011、FR-012、FR-013。

- [ ] T005 [US2] 在`tests/01_decentralized_uploading/test_issue114_storage_regions.py`新增能覆盖本故事真实边界的固定反例/交互测试，先证明已知故障可失败。
- [ ] T006 [US2] 在`backend/ingest/document_storage.py`及本目录`contracts/tool-and-source.md`约束下实现本故事，保持来源、原主模型和科学字段所有权。
- [ ] T007 [US2] 接入`backend/ingest/field_sources.py`及本故事涉及的现有宿主，运行新反例和来源保存重读/权限/恢复集成，保留前后证据。

## 阶段4：US3——RAG按权限读取（P1）

独立验收：公开RAG仅能取得批准来源，缓存不绕过权限。 覆盖FR-008、FR-009。

- [ ] T008 [US3] 在`tests/01_decentralized_uploading/test_manuscript_handoffs.py`新增能覆盖本故事真实边界的固定反例/交互测试，先证明已知故障可失败。
- [ ] T009 [US3] 在`backend/ingest/field_sources.py`及本目录`contracts/tool-and-source.md`约束下实现本故事，保持来源、原主模型和科学字段所有权。
- [ ] T010 [US3] 接入`backend/services/manuscript_handoffs.py`及本故事涉及的现有宿主，运行新反例和来源保存重读/权限/恢复集成，保留前后证据。

## 阶段5：完善与跨故事验收

- [ ] T011 在本目录`quickstart.md`登记实际测试命令/版本，执行字段契约、四宿主、变异及受影响相邻检查；已有失败用独立基线单列。
- [ ] T012 在本目录`validation.md`登记原PDF新模型调用、故障注入与工具动作、正式后处理和来源重读证据，逐项核对全部SC；未运行层明确未完成。
- [ ] T013 检查本目录`spec.md`的全部FR及`plan.md`映射，与`../232-complete-pdf-regions/delivery-framework.md`核对依赖/接口/模型/版本/权限一致性。
- [ ] T014 实现后更新`docs/overview/01_Decentralized_Uploading_of_Superconductivity_Data/pdf-parsing-pipeline.md`等实际受影响总览及本目录`validation.md`；必要时更新README，按仓库规则提交本任务；远程链接和真实验收未完成不得关闭Issue。

## 依赖与执行顺序

本轮不进入本任务列表实施。未来T001→各US测试/实现/集成→T011—T014；同文件串行。Task不代替Issue协作状态，不按文档存在或旧测试计数认定完成。

## 需求覆盖

每个FR到US及测试/实现/集成任务逐项见[Plan映射](plan.md#需求到设计与任务映射)；全部SC由T011—T013逐层核验，场景与边界见Spec和Quickstart。
