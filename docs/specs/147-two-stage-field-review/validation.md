# 验收记录

## 最新实施验收入口

人工审核通过／不通过、来源详情状态及三个模型入口现已实现；验证与边界见 [人工流程实施验证](human-review-validation.md)。下方“尚未实施”等描述保留为此前各轮记录，不代表本轮最终状态。

## 2026-10-22 结果汇总与人工说明的后续文档澄清

- 图二将末尾操作明确为“只统计通过、未通过、未完成；不重新审核”，并以 96 项复用、4 项修改说明整篇提交为何等待结果收齐。
- “同版本科学失败”改用“上次已判不通过，之后内容和依据都没改”解释；技术失败单列，可重试。图三将未修改主动核对与人工修改记录要求分开，并要求模型不通过时给出原因及真实依据或缺口。
- 原话逐字追加，5 张新截图归档后逐字节比对并解码通过；UTF-8、相对链接、三个模型入口数量与 `git diff --check` 核验通过。图源人工检查，未宣称本轮做了浏览器渲染或业务测试。
- Issue #147 与本地 Spec 同步；FR-016—018 / SC-011—013 的业务验收列入待实施 T017。本轮无业务代码、草稿或当前功能总览修改。

## 2026-10-22 人工认可与三个模型入口的文档修订

- 本轮仅更新需求文档和流程图，无业务代码或真实草稿变更；T013—T016 保持未完成。
- review-flow.md 包含三张 Mermaid 源图：上传解析、提交时调用／不调用模型、侧栏主动核对。已检查分支含义及编号，未进行浏览器图形渲染验收。
- 文档 UTF-8 无替换字符、相对链接存在、`git diff --check` 通过；两张截图与上传原文件逐字节一致且可解码。
- 图片 SHA-256：认可分支图 `3838c028d48ff5c9cda3a3885e7d438598eea6990ac8fd8753bc3fb87e0df291`；提交分支图 `d8705063976507ff58f7833e770c9ef771ee3f2a220d14ae0b2ab960e47d114f`。
- Issue #147 正文已回读确认包含“图二：点击提交后，哪些字段调用 LLM？”及“该分支没有理由输入区”；仍开放且只有 type:feature 标签。远程 Spec 文件仍待授权推送后验证。
- 下方为此前业务版本的验收，不代表本轮新人工审核流程已经实现。

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

## 2026-10-22 主动核对循环修复验证

- `test_field_review_start.py`、`test_two_stage_review.py`、`test_issue109_manual_evidence.py`、`test_property_evidence.py`：48 项通过。覆盖真实摘要/科学快照不同令牌、旧请求失败与新请求排队、快照构建期间并发修改拒绝、无证据理由进入模型请求及肯定/否定回答、仅本字段依据版本改变、模型通过结果读取后提交不排新任务。
- `two-stage-review.test.tsx`、`manual-evidence-section.test.tsx`：18 项通过。包含主动按钮保存当前人工说明、必要说明缺失时保持侧栏、任务使用草稿令牌、通过后关闭并提交复用；保留上一轮 μ* 设置保存与字段隔离测试。
- 本机 MySQL 外层回滚验证：`test_two_stage_review_mysql.py -k 'current_result_reuses or partial_results_and_failure'`：2 项通过。实际 `save_results` / `load_results` 与严格门禁路径，测试事务全部回滚。
- `npm run build` 及 `git diff --check` 通过；构建仍只有既有大分包与 3Dmol 提醒。
- 新截图已归档，原话、根因与验收见 [主动核对回归](field-review-start-regression.md)。Issue #147 已追加本轮记录，保持开放；未推送。
- 验证边界：模型响应使用可控测试回答，未在用户真实 La-Sc-H 草稿上调用模型或代为提交；没有宣称实际 μ* 已科学通过。此次没有批量修改草稿或修复全部历史核对记录。
