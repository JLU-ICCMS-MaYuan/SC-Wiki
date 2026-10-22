# 验收记录

日期：2026-10-22。验证使用 `mayuan` 工作树；真实草稿只读或复制到外层事务，未提交、批准或修改用户科学值。

## 已通过

- Python 两阶段字段、普通物性拆分、稳定键、并发保护回归：`test_two_stage_review.py` 12项相关场景通过；与现有物性/科学证据测试合计 73 项通过。人工补充证据与图片能力回归 17 项通过。
- MySQL 外层回滚：`test_two_stage_review_mysql.py` 6项（含纸面/`dos_fermi` 局部保存预算）通过；`test_two_stage_commit_mysql.py` 2项通过，失败时正式论文不变且暂存保留，通过时修改和批准原子完成。
- 字段保存性能：447项隔离草稿的纸面字段 P95 约 0.096 秒，`dos_fermi` 名称 P95 约 0.088 秒；整篇科学快照 0 次、旧证据历史读取 0 次、模型调用 0 次。
- 前端 `two-stage-review.test.tsx` 7项通过；TypeScript 构建通过。覆盖无改零请求、稳定身份、N(EF)名称/数值/单位独立、完成不启动核对、失败理由不能绕过。
- 本地 Alembic 已在当前 MySQL 应用到 `20261022_0147b`，新增管理员暂存表和结构稳定审核身份列；测试数据在事务回滚后清理。

## 兼容说明

旧的 `evidence-workflow.test.tsx` 中有若干断言仍要求旧 `/preflight`、整条记录接受和“完成”接受建议行为，这些与本 Spec 的最终要求相反，不能作为本轮失败依据；需要后续把旧测试断言迁移到 `/summary`、`/submit-check`和字段说明保存契约。

Go 旧测试 `TestApplyPaperEvidenceArchivesManualReasonInReviewTransaction` 仍期待批准后删除 `scientific_evidence_checks`，而本轮要求保留逐字段历史，因此该单条旧断言会失败；新的管理员 MySQL 原子事务测试通过。模型图片不支持时保留一次技术回退，不把图片内容伪称论文证据。

## 未覆盖限制

- 未运行真实浏览器登录后的生产认证 E2E；前端测试使用现有测试运行器。
- 未在生产部署；Issue/Spec 远程双向链接待用户授权推送后验证。
- 旧数据首次提交迁移在隔离副本验证，真实用户草稿未批量执行迁移。

## 2026-10-22 侧栏回归修复验证

- 已新增 `two-stage-review.test.tsx` 回归：字段设置即使从分项来源入口打开，也一次纵向展示名称、值、值类型、单位；μ* 的真实 `TcScientificField` 可由来源侧栏定位并保存设置；待提交状态不拼接或伪造 AI 理由。
- 目标测试：`npm run test:upload-ui -- tests/01_decentralized_uploading/two-stage-review.test.tsx`，10 项通过。
- `npm run build`（包含 `tsc -b` 与 Vite production build）通过；仅有 3Dmol 的 `eval` 提醒及大 chunk 提醒。
- `git diff --check` 通过。三张用户附件中的前两张已归档，第三张提供路径不存在，Spec 已登记该材料缺口。
