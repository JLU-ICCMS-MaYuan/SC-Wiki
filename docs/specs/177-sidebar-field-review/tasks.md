# 实施任务

依据：[Spec](spec.md)、[Plan](plan.md)、[Research](research.md)、[数据模型](data-model.md)、[契约](contracts/field-review.md)。

- [x] T001 [US1] tests/01_decentralized_uploading/ 增加字段保存与核对全局误拦截反例。
- [x] T002 [US1] frontend/src/lib/fieldDrafts.ts 与上传／管理员宿主接入字段限定保存。
- [x] T003 [US1] backend/api/evidence.py 与字段签名模块实现准备和排队隔离。
- [x] T004 [US2] backend/ingest/property_evidence.py、scientific_evidence.py 实现完成持久化及读取复用。
- [x] T005 [US2] frontend/src/components/EvidenceWorkflow.tsx 贯通自动保存、字段准备、遮罩及结果更新。
- [x] T006 [US3] 完整宿主、真实存储往返、取消／冲突／失败／候选不自动应用验证。
- [x] T007 [US3] 两条表单契约命令、受影响回归、构建、Overview／Issue 更新及精确本地提交。

映射及顺序沿 plan.md，T001 失败证据先于实现；其他入口不能放宽。
