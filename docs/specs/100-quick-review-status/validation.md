# 验收记录

日期：2026-09-10。对应 [Issue #100](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/100)。

## 复现与修复

修复前，运行快速审核三状态测试，管理员/超级管理员 × 中文/英文四种组合均失败：
实际为 `rejected,pending`，期望为 `approved,pending,rejected`。
修复将选项、分类来源及审核请求集中到共用实现，未修改 Go/Python 审核规则。

## 验证证据

| 需求 | 验证 | 结果 |
| --- | --- | --- |
| FR-001、SC-001 | 两角色、中英文三状态 UI 回归 | 顺序与选项一致 |
| FR-002、SC-002 | 待审快照、正式分类、快照 404、服务读取失败与编辑页当前选择测试 | 批准携带类型、家族及正式状态 ID；非批准不加载或提交分类 |
| FR-003/004 | 提示、失败保留、提交中禁用交互、编辑页审核与结构上传回归 | 22 项前端回归通过 |
| FR-005、SC-003 | 当前 scwiki MySQL 的 `TestCurrentMySQLQuickReview` | 两个真实角色的三个状态均通过；批准版本及每次审核历史正确；写入回滚后测试论文不存在 |
| FR-005 | 只读执行论文 #29 原有 Evidence 校验 | 仍报告物性记录缺少可解析 Evidence，没有绕过第二个问题 |
| SC-003 | TypeScript 与 Vite 构建 | 通过；保留既有 3dmol eval 与产物体积提示 |

## 浏览器与运行环境

Chromium 访问当前 Vite→Go→Python 服务，使用当前 admin 和 superadmin 各自账号，
分别检查 `/admin`、`/superadmin` 小锤子及 `/admin/papers/29/edit`：三个选项一致，提示正确。
真实调用前端共用读取模块，论文 #29 得到 conventional、一个材料家族、三个正式状态 ID
96/97/98。浏览器验证拦截所有非 GET 请求，没有审核或改写现有论文。

数据库测试使用当前 MySQL 外层事务，调用真实 Gin 身份守卫及 ReviewPaper，验证批准、
退回、拒绝和历史落库。仅事务外的发布/清理 HTTP 使用测试接收端，确认两次批准触发发布，
不向真实向量索引或文件系统发布测试论文。此项不宣称验证了向量索引发布的完整实现。
未创建临时数据库，未修改既有论文科学数据或 Evidence。

验证时开发服务已热重载本次工作树；最终提交保存同一实现。未推送远端，其他部署环境未核验。

## 文档收敛

需求、计划、契约和任务一致；Overview 已将快速审核两状态描述更新为当前三状态行为。
Issue #62/#79 的文档保留历史上下文，本次 Spec 与当前 Overview 记录修复后的事实。

## 完成核查与未通过边界（2026-09-18）

三状态恢复已经实现，但不能仅依靠初次验收认定当前流程全部完成：#103 后，编辑批准先自动保存、重新读取分类、检查现有核对结果，Go 批准事务还会调用 Python `prepare-review` 校验分类是否与已保存数据一致。

本轮既有前端审核回归 2 个文件、20 项通过；Go 的 `Test.*(Review|Evidence)` 通过。未启用当前 MySQL 专项，未重跑真实库写入或外部发布。记录分别在 `/tmp/scwiki-100-close-tests.log` 和 `/tmp/scwiki-100-close-go.log`；这些通过结果不覆盖下方组合缺口。

### 已隔离复现：旧快照覆盖管理员新分类

1. 构造待审正式详情：超导体类别为 `unconventional`，材料状态 ID 501、维度 `two_dimensional`；保留同版本上传快照，旧值分别为 `conventional`、`three_dimensional`。
2. 调用真实 `resolveReviewClassifications` 和 `paperReviewPayload`：请求得到旧类型 `conventional`、旧维度 `three_dimensional`。传入无快照的对照输入则得到新保存值。
3. 将该载荷交给真实 Python `validate_review_classifications`，用只读会话夹具提供同一份新保存值：返回 `409 evidence_stale`，提示“审核分类与已保存数据不一致，请先保存修改并重新核对”。使用新保存值的对照载荷通过。

前端仅替换未调用的网络模块，分类解析和请求构造均来自当前源码；Python 仅替换数据读取会话，使用实际生产校验函数。探针没有连接真实业务库，也不是一轮完整浏览器保存验收。源码调用链补足可达性：`AdminPaperEditPage.handleEditReview` 在保存后重新调用分类解析；`rewrite_paper_scientific_draft` 对 pending 不升版本、不改旧上传快照，读取快照时仍可通过版本校验。

证据：`/tmp/scwiki-100-classification-probe.mjs`、`/tmp/scwiki-100-classification-probe.json`、`/tmp/scwiki-100-classification-result.json`。该缺口不满足 US2、FR-002 及 SC-002/003 的组合要求，需完成 T006–T008 后重新判断；Issue 保持开放。

### 历史测试的适用范围

上方 2026-09-10 的真实 MySQL 记录描述当时实现，不能外推为当前 Python 证据准备已经验证。`quick_review_mysql_test.go` 的 HTTP 替身对所有请求返回成功，#103 后还承接批准事务内的 `prepare-review`，已不再只替换事务外发布/清理。后续回归必须覆盖实际分类一致性边界，不能把这个替身的成功当作完整批准链路成功。
