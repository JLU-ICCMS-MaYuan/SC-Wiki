# 人工通过与提交一致性验收

日期：2026-10-28。[已确认规格](approval-submit-consistency.md)，[Issue #147](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/147)。

## 结果

- 未修改但尚无核对结果的字段可直接人工确认；普通修改仍需理由、证据或无证据说明及模型核对。待处理状态不再与已通过状态共用无说明灰色按钮。
- 摘要和详情优先读取当前版本；新写入的历史版本不覆盖当前通过。有效版本的数值不因 MySQL JSON 浮点展示末位差异变成待审核。
- 指定本机任务 `c16cc627a0c04dc8ad4289624d1da80a` 的 1,111 个稳定灰色子字段已按用户明确授权记录本次确认并建立新基线，含单独确认的理论子类型例外。不是推断过去逐项点击，也不表示这 1,111 项已重新完成科学验证。
- 本机实际 HTTP 摘要：1,111 项 human_confirmed，pending_review=0，human_modified=0。超导体类别 conventional、理论子类型 calculation 均返回 human_approved、can_approve=false、stale=false。真实完整来源快照通过 resolve_results，预计模型待核对项 0。
- α²F、phDOS 独立提交绑定已符合要求，无需新增绕过代码。真实提交事务验证未采纳、needs_review 的两类谱仍保存并可重读；其他字段失败仍阻止送审。

## 验证及边界

| 检查 | 实际结果 | 对应范围 |
|---|---|---|
| 后端 pytest | 37 项通过 | 字段决定、摘要版本、基线修正、浮点往返、提交模型选择和真实谱提交 |
| 前端 Vitest | 41 项通过 | 当前/旧状态、成功关闭、失败保留、迟到响应、三种编辑宿主 |
| 真实 Chromium | 通过，模型任务 0 | 正式上传 React 路由，隔离 HTTP 夹具；未修改确认、重开刷新、修改拒绝及说明保存 |
| TypeScript 与 Vite | 构建通过 | 保留既有 3Dmol eval 和大分包警告 |
| 目标任务只读 HTTP | 摘要及两个指定字段详情一致 | 验证本机运行代码，不代为点击真实表单 |
| 完整提交字段门禁 | 1,111 项通过，待模型项 0 | 调用实际快照/门禁函数；未执行真实论文提交 |
| 定向修正幂等 | 重跑不新增决定或事件 | 仅已授权任务 |

后端文件：`test_field_decisions_mysql.py`、`test_review_baseline_repair_mysql.py`、`test_two_stage_review.py`、`test_field_review_start.py`、`test_spectrum_submit_mysql.py`，位于 `tests/01_decentralized_uploading/`。真实 MySQL 测试使用外层事务回滚；谱提交使用随机 Redis 键，清理自有键及索引。只隔离临时文件发布/收尾，字段门禁、论文持久化、谱绑定和重读均走生产函数。失败测试先证明缺少新状态契约，再验证修复结果。

前端命令：在 `frontend/` 执行 `npm run test:upload-ui -- ../tests/01_decentralized_uploading/approval-state.test.tsx ../tests/01_decentralized_uploading/two-stage-review.test.tsx ../tests/01_decentralized_uploading/paper-field-settings.test.tsx`；构建命令 `npm run build`。

浏览器脚本：`tests/01_decentralized_uploading/human-field-review-browser.mjs`，使用本机 Chrome 与打包 Playwright，所有页面 API 在隔离上下文拦截。截图见 [通过后](assets/2026-10-28-approved-sidebar.png)、[修改拒绝](assets/2026-10-28-modified-refusal.png)。这证明交互行为，不冒充用户之前操作的完整复现。

## 数据修正与备份

执行工具：`scripts/repair-upload-review-baseline.py`。固定目标、默认只盘点；`--apply` 对比审核/内容/来源/事件版本，数据库事务内保存决定和新基线，再同步 Redis 并回读。没有修改其他任务、科学字段值、PDF、谱曲线或原始编辑事件。

清单、全量修正前审核记录和上传持久记录、Redis 原状态/草稿、备份哈希、执行结果及回读报告保存在 `.data/147-review-baseline-20261028/`。原始备份 `before.json` 的 SHA-256 为 `0123c6d30cfe1a922b2ce111eb2d7f4339ed17a41d76c14be8120fef96e1e252`。精简结果归档于 [核验结果](assets/2026-10-28-approval-verification.json)。

第一次写入后，回读发现新基线中结构角度 `120.00000000000001` 在 MySQL JSON 读成 `120.0`。原草稿未变；按冻结清单将新增基线改为精确规范化表示，重读与幂等验证通过。旧事件完整保留，新增数值回归覆盖该问题。该修正不触碰论文原值或旧事件。

本轮不改 PDF 文字提取、字段提取或谱数字化，不调用模型重新提取；验收范围是已确认的审核/提交行为和一次性历史修正，不能称为整篇解析或整站验收。工作区其他解析及谱拖动并行改动保留，未混入本次提交。Issue 远程 Spec 链接仍待授权推送后验证，不关闭 Issue。
