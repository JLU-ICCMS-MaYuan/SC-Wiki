# 技术任务

输入：[Spec](spec.md)、[Plan](plan.md)、[Research](research.md)、[契约](contracts/sidebar.md)。

- [x] 字段提示规则及相关历史已迁移至 [#220](../220-field-red-marking/spec.md)，本处不再独立定义。
- [x] T002 实现frontend/src/lib/evidenceOwnership.ts的稳定所属映射，保护独立科学身份。
- [x] 字段提示规则及相关历史已迁移至 [#220](../220-field-red-marking/spec.md)，本处不再独立定义。
- [x] T004 修改EvidenceWorkflow.tsx的子项选择及未应用保护；各子项来源和操作独立。
- [x] T005 在field-sidebar-ownership.test.tsx覆盖四宿主、只读、重排、当前字段请求；更新scripts/check-form-contract.mjs并运行规定回归与构建。
- [x] T006 写validation.md，回写Overview、README与表单清单，核对任务字节后提交并更新Issue；远程Spec发布门未满足不关闭。

依赖：T001→T002→T003→T004→T005→T006。FR-001/002对应T002/003/005；FR-003/005对应T004/005；FR-004对应T003/005；FR-006与SC-001至003对应T005/006。任务勾选仅代表技术事实，不作为独立协作状态。
