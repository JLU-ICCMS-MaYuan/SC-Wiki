# 技术任务

输入：[规格](spec.md)、[计划](plan.md)、[研究](research.md)、[契约](contracts/review.md)。

- [x] T001 完成 `docs/specs/100-quick-review-status/` 规划与需求门，关联 Issue。
- [x] T002 [US1] 在 `tests/01_decentralized_uploading/admin-paper-classification-review.test.tsx` 先复现缺少批准，补两角色、分类载荷、失败保持和三状态验证。
- [x] T003 [US1] [US2] 在 `frontend/src/lib/paperReview.ts`、`frontend/src/components/PaperReviewStatusSelect.tsx`、两个管理员页面和中英文 admin 词典统一审核逻辑及提示，补编辑页回归。
- [x] T004 在 `goserver/handlers/quick_review_mysql_test.go` 通过当前 MySQL 验证审核与回滚，运行前端回归、构建及浏览器只读选项验证，将证据写入 `validation.md`。
- [x] T005 回写 `docs/overview/02_Decentralized_Maintenance_and_Verification/literature-and-record-review.md`，更新 Issue 文档影响并自动提交。

依赖 T001→T002→T003→T004→T005，串行执行。US1/US2 共用数据和选择器构成最小交付。
FR-001/002 与 SC-001/002 对应 T002/T003/T004；FR-003/004 对应 T002/T003；FR-005 与 SC-003 对应 T004。

## 当前收敛任务（2026-09-18）

T001–T005 保留初次修复记录；后续 #103 的保存与证据一致性规则引入新的组合边界，当前核查证据见 [validation.md](validation.md)。

- [x] T006 [US2] 补充同版本旧上传快照下“修改分类→保存→重新加载→批准”的跨前后端回归，覆盖超导体类别与材料维度，确保使用新保存值；保留无快照回退及读取失败阻断。
- [x] T007 [US1] [US2] 收敛正式分类与上传快照的事实来源，消除旧快照覆盖新保存值；复核快速审核与编辑审核，不绕过分类和证据一致性校验。
- [x] T008 验证真实 `prepare-review` 分类边界，避免通用成功响应替身掩盖拒绝；补齐通过后的验收与 Overview，再核对 Issue 关闭条件。

覆盖：US2、FR-002/005、SC-002/003 → T006–T008；FR-006 → T009/T010。用户已确认管理员保存时创建新家族，全部收敛回归已通过，证据见 validation.md。

- [x] T009 [US1] [US2] 确认家族目录创建时机，补齐材料/结构家族保存、初次待审回填及清空重载语义，使用非空家族验证完整批准契约；不以只通过类型/维度回归代替全范围完成。

- [x] T010 [US2] 修复 `backend/services/scientific_draft_rewrite.py` 同值判断漏掉论文级类型/家族，以及 `backend/api/rag.py` 科学保存漏写已有家族关联；以 `tests/01_decentralized_uploading/test_review_classification_save.py` 验证只改分类、重开和重复保存。来源：FR-002/005；属于主路径实现遗漏，新目录创建仍由 T009 决定。本项通过隔离 SQLite 真实事务；完整 MySQL 与首次回填验收也已通过。
