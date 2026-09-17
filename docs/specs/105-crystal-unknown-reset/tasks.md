# 实施任务：晶系未知联动

输入：[Spec](spec.md)、[Plan](plan.md)、[Research](research.md)、[数据模型](data-model.md)、[契约](contracts/form.md)。

## 阶段一：准备与基础

- [x] T001 核对 Issue #105、保存开工状态与重叠文件备份，完成 `docs/specs/105-crystal-unknown-reset/` 文档门。

## 阶段二：US1（P1，完整 MVP）

- [x] T002 [US1] 在 `tests/01_decentralized_uploading/crystal-unknown-reset.test.tsx` 增加真实控件交互失败测试，覆盖选择、重复选择、输入缓存、多状态、只读、正向联动、核对通知。
- [x] T003 [US1] 在 `frontend/src/components/MaterialStatesEditor.tsx` 实现一次三字段更新及重复选择处理。
- [x] T004 [US1] 在 `tests/01_decentralized_uploading/test_crystal_unknown_reset.py` 验证归一化、科学保存、隔离数据库重读不恢复旧值。
- [x] T005 [US1] 在 `tests/01_decentralized_uploading/crystal-unknown-browser.mjs` 验证上传和审核页面的鼠标/键盘操作、保存请求、失败重试及刷新；运行相关回归、类型检查和构建。

## 阶段三：收尾

- [x] T006 更新 `docs/overview/01_Decentralized_Uploading_of_Superconductivity_Data/data-structure-and-form-mapping.md` 和 `docs/overview/02_Decentralized_Maintenance_and_Verification/literature-and-record-review.md`，将验证证据写入 `quickstart.md`；同步 Issue，按安全分离结果处理提交。

## 依赖与覆盖

T001 → T002（确认预期失败）→ T003 → T004、T005 → T006。同一文件串行；不需要子代理。
FR-001/002 由 T002、T003、T005 覆盖；FR-003 由 T004、T005 覆盖；FR-004/005/006 由 T002、T005 覆盖。
SC-001/002/003 的证据统一记录于 quickstart。本功能只有一个用户故事，无额外增量。
