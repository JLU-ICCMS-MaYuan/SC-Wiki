# 技术任务

输入：[规格](spec.md)、[计划](plan.md)、[研究](research.md)、[契约](contracts/review.md)。

- [x] T001 完成 `docs/specs/100-quick-review-status/` 规划与需求门，关联 Issue。
- [x] T002 [US1] 在 `tests/01_decentralized_uploading/admin-paper-classification-review.test.tsx` 先复现缺少批准，补两角色、分类载荷、失败保持和三状态验证。
- [x] T003 [US1] [US2] 在 `frontend/src/lib/paperReview.ts`、`frontend/src/components/PaperReviewStatusSelect.tsx`、两个管理员页面和中英文 admin 词典统一审核逻辑及提示，补编辑页回归。
- [x] T004 在 `goserver/handlers/quick_review_mysql_test.go` 通过当前 MySQL 验证审核与回滚，运行前端回归、构建及浏览器只读选项验证，将证据写入 `validation.md`。
- [x] T005 回写 `docs/overview/02_Decentralized_Maintenance_and_Verification/literature-and-record-review.md`，更新 Issue 文档影响并自动提交。

依赖 T001→T002→T003→T004→T005，串行执行。US1/US2 共用数据和选择器构成最小交付。
FR-001/002 与 SC-001/002 对应 T002/T003/T004；FR-003/004 对应 T002/T003；FR-005 与 SC-003 对应 T004。
