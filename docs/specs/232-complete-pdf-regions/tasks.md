# 技术任务：可靠定位PDF区域并生成含完整图注的高清裁剪

输入：[spec.md](spec.md)、[plan.md](plan.md)、[research.md](research.md)、[data-model.md](data-model.md)、[接口契约](contracts/tool-and-source.md)。协作状态以[Issue #232](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/232)为准。

**本轮按后续授权实施。勾选表示所述工程动作有代码及验证证据；不等于所有模型或整篇业务验收通过。**

## 阶段1：准备

- [x] T001 在本目录`spec.md`与`../232-complete-pdf-regions/conversation.md`对照完整原话、模型/存储替代结论和已有依赖，固定来源及验收样本。

## 阶段2：US1——完整发现与首次裁图（P1）

独立验收：首次完整图可直接对照原PDF逐项检查。 覆盖FR-001、FR-002、FR-003、FR-004。

- [x] T002 [US1] 在`backend/tests/test_pdf_regions.py`新增能覆盖本故事真实边界的固定反例/交互测试，先证明已知故障可失败。
- [x] T003 [US1] 在`backend/ingest/pdf_regions.py`及本目录`contracts/tool-and-source.md`约束下实现本故事，保持来源、原主模型和科学字段所有权。
- [x] T004 [US1] 接入`backend/ingest/chart_reading.py`及本故事涉及的现有宿主，运行新反例和来源保存重读/权限/恢复集成，保留前后证据。

## 阶段3：US2——高清局部与多类来源（P1）

独立验收：实际图片尺寸、坐标和必要标签均可核验。 覆盖FR-005、FR-006、FR-007、FR-010、FR-011。

- [x] T005 [US2] 在`backend/tests/test_pdf_regions.py`及`backend/tests/test_image_feedback.py`新增能覆盖本故事真实边界的固定反例/交互测试，先证明已知故障可失败。
- [x] T006 [US2] 在`backend/ingest/chart_reading.py`及本目录`contracts/tool-and-source.md`约束下实现本故事，保持来源、原主模型和科学字段所有权。
- [x] T007 [US2] 接入`backend/ingest/document_regions.py`及本故事涉及的现有宿主，运行新反例和来源保存重读/权限/恢复集成，保留前后证据。

## 阶段4：US3——特殊版式与定位一致（P1）

独立验收：旋转、裁剪框偏移和跨页限制均可追查。 覆盖FR-008、FR-009、FR-012、FR-013、FR-014。

- [x] T008 [US3] 在`backend/tests/test_chart_reading.py`新增能覆盖本故事真实边界的固定反例/交互测试，先证明已知故障可失败。
- [x] T009 [US3] 在`backend/ingest/pdf_regions.py`及本目录`contracts/tool-and-source.md`约束下实现本故事，保持来源、原主模型和科学字段所有权。
- [x] T010 [US3] 接入`backend/ingest/pdf_evidence_crops.py`及本故事涉及的现有宿主，运行新反例和来源保存重读/权限/恢复集成，保留前后证据。

## 阶段5：完善与跨故事验收

- [x] T011 在本目录`quickstart.md`登记实际测试命令/版本，执行字段契约、四宿主、变异及受影响相邻检查；已有失败用独立基线单列。
- [x] T012 在本目录`validation.md`登记原PDF新模型调用、故障注入与工具动作、正式后处理和来源重读证据，逐项核对全部SC；未运行层明确未完成。
- [x] T013 检查本目录`spec.md`的全部FR及`plan.md`映射，与`../232-complete-pdf-regions/delivery-framework.md`核对依赖/接口/模型/版本/权限一致性。
- [x] T014 实现后更新`docs/overview/01_Decentralized_Uploading_of_Superconductivity_Data/pdf-parsing-pipeline.md`等实际受影响总览及本目录`validation.md`；必要时更新README，按仓库规则提交本任务；远程链接和真实验收未完成不得关闭Issue。

## 依赖与执行顺序

本轮已按此顺序实施：T001→各US测试/实现/集成→T011—T014；同文件串行。Task不代替Issue协作状态，不按文档存在或旧测试计数认定完成。

## 需求覆盖

每个FR到US及测试/实现/集成任务逐项见[Plan映射](plan.md#需求到设计与任务映射)；全部SC由T011—T013逐层核验，场景与边界见Spec和Quickstart。

## 2026-11-10 恢复实施

用户后续明确要求：

> 开始落地完成 232， 233,234， 235

采用本次后续授权恢复实施，替代上一轮仅文档的执行限制；历史原话保留。四项现行FR/SC不变，依次验证并更新实际任务。远程Spec未推送保持待验证，不自动push或部署。

## 本轮验收边界

所有已勾项的证据和失败边界见[validation.md](validation.md)。真实GPT局部新提取及正式填写/JSON保存重读通过；Flash能输入图片和调用工具，但Y-H科学读数未通过；官方OpenAI账号端点与MySQL并发未实测，不宣称整篇五阶段通过。远程Spec未push，Issue保持OPEN。
