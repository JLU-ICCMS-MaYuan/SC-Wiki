# 拆分前历史材料与独立功能导航

2026-11-04，用户认可将原六个目标按功能拆分。GitHub [#213](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/213)已转为type:epic，仅保存共同背景、约束及子项导航，不再承载合并Feature Spec。

## 当前独立规格

| 原目标 | 子Issue | 类型 | 独立Spec | 原总规格范围 |
| --- | --- | --- | --- | --- |
| 1 | [#214](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/214) | type:feature | [统一拒绝返修流程，保持旧批准版公开](../214-rejected-paper-revision/spec.md) | FR-001、FR-002 |
| 2 | [#215](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/215) | type:feature | [审核列表标题自适应宽度并支持悬停全文](../215-paper-title-display/spec.md) | FR-003 |
| 3 | [#216](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/216) | type:feature | [检查列表分页与独立工作区](../216-review-list-pagination/spec.md) | FR-004 |
| 4 | [#217](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/217) | type:bug | [统一收录贡献名称，消除作者身份歧义](../217-contribution-paper-labels/spec.md) | FR-005 |
| 5 | [#218](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/218) | type:bug | [合并重复权限提示并统一禁写状态](../218-workdraft-permission-feedback/spec.md) | FR-006 |
| 6 | [#219](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/219) | type:feature | [研究材料右侧可折叠大纲](../219-material-state-outline/spec.md) | FR-007、FR-008 |

每个子目录独立保存Spec、Plan、Research、Tasks、Quickstart、Validation、界面/接口契约和需求检查表；涉及实体不变量的目标另有data-model.md。目标①/⑤共享权限契约，②/③共用列表组件，各自独立验收。

## 历史与证据

- [原总规格](spec.md)、[原计划](plan.md)、[原技术拆解](tasks.md)、[原验收](validation.md)保留完整旧正文，统一加历史说明。
- 业务实现提交仍为53c32542bca1f7ea80143d563db13498ba210812，本轮不拆改Git历史或重新实施。
- [六张原图索引](assets/images.json)、原图、界面截图和[原机器摘要](assets/checks.json)保持原字节内容；各子项只建立证据引用，避免重复复制。
- [功能映射](split-map.json)登记旧FR/SC→子Issue/Spec/代码与证据归属，不保存本地Issue协作状态。
- 本轮检查见assets/split-verification.json；没有重跑业务测试，原共用通过数不重复算到各子项。
- 远程Spec尚未推送，真实协作状态以GitHub为准。
