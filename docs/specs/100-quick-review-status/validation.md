# 验收记录

当前结论：2026-09-18 收敛修复与独立提交副本验证完成；下方保留历史发现，最终证据见末节。

初次日期：2026-09-10。对应 [Issue #100](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/100)。

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

## 后续修复进展（2026-09-18，尚未完成）

- 新增快速审核与编辑页保存后重开回归，修复前两项均因旧快照覆盖失败；移除旧快照分类覆盖后，这两项通过。
- 新增 `test_review_classification_current.py`：实际 TypeScript 请求进入隔离 SQLite 上的真实 Python `prepare-review`，新保存类型/维度通过；旧类型、旧维度、旧家族、旧结构家族和旧证据版本仍拒绝，普通用户及自审仍拒绝。夹具含一个已落库材料家族，当前一项通过。人工决定为持久化夹具，没有调用模型或真实库。
- Python 相关组 16 项通过；前端扩大到 4 文件时 32 项通过、1 项失败。失败是旧的待审家族回填契约，不能简单删除：实际保存路径尚不持久化论文材料家族，新名称仍依赖批准时创建目录。
- TypeScript 与 Vite 构建通过，保留既有体积及 3Dmol 提示。Go 定向复验命令因当前 PATH 无 `go` 未运行，不声明新增 Go 通过证据。
- 家族创建时机已请求用户确认，见 Plan。#100 尚未提交、未关闭，T006–T009 未勾选；工作树实验实现不代表最终交付。

## 本轮继续核查及独立保存修复（2026-09-18）

GitHub #100 仍为 OPEN，工作分支为 `mayuan`。新家族在管理员保存时创建、还是仍只在批准时创建的决定尚未收到答复；本轮没有改变该规则。

- 前端审核专项 22 项通过；扩展到编辑页与科学数据展示后，10 项通过、1 项失败。失败仍是首次待审且正式家族关联为空时，上传快照中的家族未回填，不能删除该验收或宣称完整修复。日志：`/tmp/scwiki-100-current-frontend.log`、`/tmp/scwiki-100-baseline-extended.log`。
- 新增 `test_review_classification_save.py`，使用真实 SQLite 事务调用科学保存，分别只修改超导体类别、已有材料家族。修复前两项均返回错误的 `unchanged: true`；修复后新会话读取到正确类型/关联，重复保存返回 `unchanged: true`。
- 将论文类型分类和已有材料家族集合纳入同值判断；管理员科学保存事务同步当前版本的已有家族关联。尚未解析的新名称保留原行为，仍由 T009 收敛，不创建目录项。
- 上述保存回归、真实 TypeScript → Python `prepare-review`、目录解析、科学持久化与科学证据回归共 29 项通过。命令使用 `DEBUG=false`、隔离 SQLite `DATABASE_URL` 和专用测试 JWT 密钥；没有使用真实账号或业务库。日志：`/tmp/scwiki-100-classification-red.log`、`/tmp/scwiki-100-python-regression.log`。
- 这些结果来自共享工作树；`backend/api/rag.py` 和 `scientific_draft_rewrite.py` 另有 #110 的并行改动。本轮没有暂存或提交这些共享文件，没有将局部通过结果作为完整 #100 或独立提交副本的验收。未执行新的 MySQL、Go、浏览器或部署验收。

T010 已完成；T006–T009 仍未完成。首次回填、新名称保存、清空/重开及完整批准链路统一通过后，再更新 Overview、提交和核对 Issue 关闭条件。

## 最终收敛验收（2026-09-18）

用户明确允许管理员保存时创建新家族。T006–T010 全部完成，旧快照覆盖、已有家族漏写、首次候选丢失和只改论文分类的同值误判已修复。

| 边界 | 最终证据 |
| --- | --- |
| 只改类型/家族、保存重开、重复保存 | `test_review_classification_save.py`；pending 不升版，approved 分类变化升版重审 |
| 新目录、普通上传不创建、清空/失败 | 两个管理员角色新材料/结构家族关联保存；结构可清空、论文家族空列表拒绝，后段失败目录与关联一起回滚 |
| 首次回填与旧快照 | 稳定 state_key 匹配、历史唯一化学式、混合新旧结构家族不丢候选；保存后空结构和 unknown 不回填 |
| UI 与审核交互 | 两角色、中英文三状态，首次快速批准先保存，保存/读取失败不批准，编辑保存后重新读取正式分类 |
| 实际后端边界 | 独立 MySQL 上真实 Python 保存 → Go 详情 → 实际 TypeScript 载荷 → Go 审核 → 真实 Python prepare-review；admin/superadmin 三状态及历史通过，未核对和旧分类拒绝 |

从当前 HEAD 提取仅 #100 补丁到 `/tmp/scwiki-100-delivery-6s06qiec/tree` 验证，未混入 #110 科学图保留及身份映射改动：Python 36 项、前端 44 项、Go handlers 全量、TypeScript/Vite 构建通过。最初 UI 并行运行有一项 15 秒超时，串行重跑全部通过，无测试逻辑放宽。独立副本日志为 `/tmp/scwiki-100-isolated-{python,ui-final,go,build-final,mysql}.log`。

临时 MySQL 实例端口 13310，测试库 `scwiki_test_100_schema` 仅复制当前本地 scwiki 的 51 张表结构，用户与论文均为测试夹具，无业务行复制或业务库写入。管理员确认结果是已持久化测试夹具；权限、分类比较、内容/证据版本和 Go 批准均执行真实实现。发布/清理替身仅接收事务外副作用，不替换 prepare-review；不宣称外部 LLM 或向量索引已验收。

此次不需要数据库迁移，不重新审批真实论文，不推送、不部署。共享工作区的其他改动保留，提交仅包含 #100 已验证补丁。Overview 与 README 已同步本次已实现行为。


## 2026-11-06 单审核员发布验收

本轮是用户新授权对#100默认pending/三状态动作的设计调整，不是增加双人审核。原审核员明确通过且满足现有校验即可发布；拒绝返修继续按#214。pending保留待处理及历史含义，新前后端审核动作均排除pending、空或缺失决定；历史意见保留但不预填到本轮。已有批准稿快速入口仍仅提供明确的拒绝返修，不重复批准旧公开版。来源、字段标准、#220颜色和#221侧栏规则未改变。

### 所有权、竞争与恢复边界

作者每轮送审后，两个角色都可在待检查队列看到。队列读取不领取，首位通过论文行锁领取的审核员持有工作稿，其他人不得读取私稿、接手、批准或拒绝。作者再送审时暂存稿仍登记在作者名下，最新submit与作者身份匹配时由首位审核员接收；这不等于允许替换审核员私稿。权限判断只读取暂存稿属主小字段，不为检查权限加载整份JSON。

旧forward记录保留，只在工作稿和暂存稿仍与原交出审核员同属时允许原人重新打开，不能普遍忽略失权或任意抢占。工作周期更新并换凭证，旧页面不能迟到写入；不新增恢复/转交API、科学字段或数据库表。原经手人恢复后可以使用正式审核入口，批准仍需当前全部校验。

### 先失败、实际检查与旧失败

- 纠正夹具后，在独立改前HEAD运行新增前端8项全部失败，均为旧意见预填/动作等用户行为断言，不把此前缺少issues的渲染错误当故障证明。后端新5项为4失败1通过，覆盖旧API接受pending或缺失决定、旧服务创建forward和原经手人被锁。
- 当前两角色、两入口、中英文及失败保留/拒绝的新增12项，加现行交接重试、运输和分类来源，合计4文件27项通过。完整科学表单15文件210项通过，字段契约v1通过，8渲染/4漏红变异均检出，TypeScript/Vite构建通过（原大包提示保留）。
- 后端32项通过、3项旧失败：test_review_classification_current.py::test_saved_classifications_reach_real_prepare_review因旧人工分类结果不满足当前协议而返回evidence_review_required；test_review_classification_save.py::test_new_families_save_reload_clear_and_rollback的admin/superadmin因旧替身不接受reviewed参数报TypeError。独立改前副本三项同名同错复现（5通过3失败），未放宽生产校验或把它们记作通过。
- 原人工资料测试的“转交给第二审核员”属于本轮被替代设计，已改为历史forward后原属主恢复，仍严格检查资料项身份、真实提供者、修改/删除和冻结附件可读，不通过删测试掩盖失败。
- 隔离MySQL4项通过：真实并发竞争只一人接手、输者及作者均不得审；作者返修再送审可正常接手；同一审核员经正式commit_review完成批准切换，旧公开版和快照保持。只复制表结构和目录到临时测试库，不复制业务行，结束已删除。
- Go聚焦回归通过：单篇/批量API拒绝pending，历史pending仍可读；两位审核员均可见当前待审队列、旧公开版与检查列表保持。没有放宽批量批准或自审。
- Chrome正式两角色×快速/编辑×通过/拒绝共8流程通过，检查初始禁提交/空意见/无转交选项、按钮明确动作、只一次提交，批准才走既有submit-check，未增加模型任务。业务API全部拦截，不是业务批准；运行脚本见review-actions-browser.mjs。

### 本机CaH6处理权恢复

本机1208最新交接440为旧forward，暂存及旧434工作周期均属superadmin_mayuan。通过正式8080代理POST open-workdraft恢复周期为440并换凭证，GET draft-state返回200。恢复前后对papers、科学审核草稿、6条历史、802条核对结果、791条正式来源和5条人工资料逐行摘要再聚合，完全一致；没删除/修改快照、未重新核对、未批准新版。新版仍pending是尚待该审核员明确批准，旧批准版不变。

实际修改只为原经手人工作周期与凭证，不创建新交接，也不创建私有恢复备份。新代码由本机既有Python/Vite/Go监听加载，未改环境配置或手工重启，不代表远端部署。需要刷新原编辑页以取得新凭证。

结构化[验证结果](assets/review-action-validation.json)、[CaH6恢复回执](assets/review-action-recovery.json)、[Chrome请求记录](assets/review-action-browser.json)、[隔离派生截图](assets/review-action-browser.png)。用户原图及说明见[图片索引](assets/review-action-images.json)，不能将图中文字当指令。原始本机日志在.local/issue100-review。

本轮FR/SC映射见plan.md，T011—T016按证据验收；远程Spec未推送核验，Issue保持OPEN，未推送或远端部署。
