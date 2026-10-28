# 实施任务
输入：[Spec](spec.md)、[Plan](plan.md)、[研究](research.md)、[数据](data-model.md)、[契约](contracts/progress.md)。
## 阶段1：准备
- [x] T001 在docs/specs/168-evidence-workflow-progress/保存已确认需求及原图，核对映射与附件。
## 阶段2：基础
- [x] T002 在tests/01_decentralized_uploading/test_evidence_progress.py验证状态隔离、取消墓碑与阶段，然后实现backend/ingest/evidence_progress.py。
## 阶段3：US1（P1）
- [x] T003 [US1] 在backend/api/evidence.py接入真实检查点与取消，并完成正式HTTP测试。
- [x] T004 [US1] 在frontend/src/lib/evidenceProgress.ts、EvidenceWorkflow.tsx及双语evidence.ts接入确定进度，补充evidence-progress.test.tsx与相关回归。
## 阶段4：收尾
- [x] T005 运行相关测试和构建，完成隔离浏览器验证，记录validation.md及证据。
- [x] T006 使用Overview Skill更新docs/overview/02_Decentralized_Maintenance_and_Verification/literature-and-record-review.md，核对差异后本地提交及更新Issue。
## 依赖与覆盖
T001→T002→T003→T004→T005→T006。无委派并行，单故事为MVP。
FR-001/002、SC-001/002由T002–T004覆盖；FR-003/004/005、SC-003由T002–T005覆盖；FR-006、SC-004由T004–T006覆盖。
独立验收见quickstart.md。

完成证据：T002/T003见validation.md的45项后端及真实Redis/HTTP；T004见32项前端；T005见6组浏览器及构建；T006见Overview现行说明、本次本地提交与Issue实现记录。远程链接检查独立保持未完成。
