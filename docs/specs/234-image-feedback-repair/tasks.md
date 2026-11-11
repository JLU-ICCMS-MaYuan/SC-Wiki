# 技术任务：以可定位证据驱动同一主模型自动重读和修复

输入：[spec.md](spec.md)、[plan.md](plan.md)、[research.md](research.md)、[data-model.md](data-model.md)、[接口契约](contracts/tool-and-source.md)。协作状态以[Issue #234](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/234)为准。

**本轮按后续授权实施。勾选表示所述工程动作有代码及验证证据；不等于所有模型或整篇业务验收通过。**

## 阶段1：准备

- [x] T001 在本目录`spec.md`与`../232-complete-pdf-regions/conversation.md`对照完整原话、模型/存储替代结论和已有依赖，固定来源及验收样本。

## 阶段2：US1——自己定位并修复问题（P1）

独立验收：已知错裁剪被发现并产生真实新区域及依据。 覆盖FR-001、FR-002、FR-003、FR-004、FR-005。

- [x] T002 [US1] 在`backend/tests/test_image_feedback.py`新增能覆盖本故事真实边界的固定反例/交互测试，先证明已知故障可失败。
- [x] T003 [US1] 在`backend/ingest/image_feedback.py`及本目录`contracts/tool-and-source.md`约束下实现本故事，保持来源、原主模型和科学字段所有权。
- [x] T004 [US1] 接入`backend/ingest/chart_reading.py`及本故事涉及的现有宿主，运行新反例和来源保存重读/权限/恢复集成，保留前后证据。

## 阶段3：US2——判断修复是否可靠（P1）

独立验收：复算与科学条件对应都通过，缺失/冲突仍有准确结论。 覆盖FR-006、FR-007、FR-008、FR-009、FR-010、FR-011、FR-012。

- [x] T005 [US2] 在`backend/tests/test_image_feedback.py`新增并重跑既有轴反序回归，能覆盖本故事真实边界的固定反例/交互测试，先证明已知故障可失败。
- [x] T006 [US2] 在`backend/ingest/chart_reading.py`及本目录`contracts/tool-and-source.md`约束下实现本故事，保持来源、原主模型和科学字段所有权。
- [x] T007 [US2] 接入`backend/ingest/model_review.py`及本故事涉及的现有宿主，运行新反例和来源保存重读/权限/恢复集成，保留前后证据。

## 阶段4：US3——失败恢复不丢成果（P1）

独立验收：同任务模型、历史、成功结果和图像关联可核对。 覆盖FR-013、FR-014、FR-015。

- [x] T008 [US3] 在`backend/tests/test_image_feedback.py`新增并重跑既有目标范围回归，能覆盖本故事真实边界的固定反例/交互测试，先证明已知故障可失败。
- [x] T009 [US3] 在`backend/ingest/model_review.py`及本目录`contracts/tool-and-source.md`约束下实现本故事，保持来源、原主模型和科学字段所有权。
- [x] T010 [US3] 接入`backend/ingest/structure_reading.py`及本故事涉及的现有宿主，运行新反例和来源保存重读/权限/恢复集成，保留前后证据。

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

所有已勾项的证据和失败边界见[validation.md](validation.md)。真实GPT局部新提取及正式填写/JSON保存重读通过；Flash此前仅图片/工具通过，现已补齐本篇38读数及正式后处理/保存重读科学门（见../234-image-feedback-repair/flash-fig4-scientific-validation.md）；官方OpenAI账号端点未实测；MySQL并发已在独立实例补齐，不宣称整篇五阶段通过。远程Spec未push，Issue保持OPEN。

- [x] T015 继续收敛Flash的Y-H实际图像坐标/材料归属与科学读数，按原主模型保留失败和新证据；正确读数通过正式后处理与保存重读后再勾选T012。不能改为换模型或降低科学验收条件。

## MySQL与旧失败补验收

- [x] T016 按用户对MySQL跳过/旧基线的标注补验收：独立实例运行原六项及79项扩展，修正七项过期夹具，隔离源码综合525项通过；保留失败前后证据、业务库准入和清理记录。详见[共享补验收](../232-complete-pdf-regions/mysql-and-baseline-validation.md)。不替代Flash、官方账号、整篇或远程门。

- [x] T017 修复真实目录预算及旧观察混入：完整父表覆盖单元格后目录1308→215，保留全文/图片，225154→70814估算token；原始上下文及版本化动作缓存回归、共享/独立102项及原PDF5条标定/IR重读通过。详见catalog-budget-fix.md，完整五阶段仍待继续。


- [x] T018 前置盘点错误接入真实原页/整图反馈，保留原保护、有效页、不重复无新依据；实际Flash重复框失败及回归先检出。
- [x] T019 原主模型使用无标签像素几何观察，完成Flash本篇38读数及原图独立参照；正式新提取/整理、ScH6共同参数/约数/来源保存重读通过，原脚本故障和复用边界另留。见flash-fig4-scientific-validation.md。

T012/T015后续依据：2026-11-11同Flash 13次新读图＋2次真实提取/整理，38独立原位图参照及ScH6共同参数/约数/来源保存重读通过；官方账号、整篇与远程门仍未验收，不据此关闭Issue。

- [x] T020 恢复US3/FR-005/012结构报告完整性：真实38→1及双结构PDF先检出；完整快照与独立来源一对一检查、无进展识别后，原SI同GPT7次新调用两份报告均38条，32有效/6疑点、JSON/CIF重读及最新源码固定重放通过。共享/独立118项通过，未拼接旧科学答案、未扩增动作轮数；整篇和业务验收仍未完成，见#224结构请求验证。

- [x] T021 按用户2026-11-11澄清以稳定失败身份进行局部结构修订，成功项冻结复用并留证；先失败后回归、隔离110、四宿主233、12变异和真实Flash原SI验证见validation.md。完整双模型业务验收仍未完成。
