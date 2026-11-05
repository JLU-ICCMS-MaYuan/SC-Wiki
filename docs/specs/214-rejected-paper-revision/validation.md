# 验收记录：统一拒绝返修流程，保持旧批准版公开

## 来源与时间

原实现及业务测试来源：本地提交 53c32542bca1f7ea80143d563db13498ba210812，原记录见[拆分前验收](../213-review-workspace-navigation/validation.md)与[机器摘要](../213-review-workspace-navigation/assets/checks.json)。
2026-11-04本轮只拆分Issue和文档，核对代码/用例哈希、图片及关系；没有重跑业务套件，不宣称独立新执行。

## 本项实际覆盖

原提交的隔离MySQL公开稿生命周期与RR并发3项、Go大JSON MySQL1项，实际Go筛选/公开保护及拒绝入口用例；共享计数不等于本项独立计数。

### 可定位案例

- `test_213_rejection_of_published_paper_preserves_public_and_returns_only_author`
- `test_213_handoff_listing_has_no_independent_revision_write_route`
- `TestRejectedRevisionAppearsInPrivateFilterWhileApprovedPaperStaysPublic`
- `TestWorkflowPrivateStatusWithLargeSnapshotsMySQL`
- `已批准稿从小锤子拒绝，不先领取已交出的工作稿`

### 代码与证据归属

具体源文件、源哈希、原FR/SC、图片、截图和测试名称见[assets/evidence.json](assets/evidence.json)。共享文件只承接本项目标的段落，150项表单、8项变异和其他共享总数只作为共同保护，不累加成本项独立数。

## 邻接已有失败

- `返修共享表单 暂存只保存草稿；重新提交使用最新草稿版本并回到同一篇论文`
- `返修共享表单 保存冲突保留用户输入，不继续送审`
- `backend/tests/test_paper_revisions.py::test_failure_after_revision_bump_rolls_back_everything`
- `backend/tests/test_paper_revisions.py::test_full_graph_roundtrip_preserves_structures_sources_and_history`
- `backend/tests/test_paper_revisions.py::test_structure_metadata_change_conflicts_even_without_paper_revision_change`
- `backend/tests/test_paper_revisions.py::test_revision_structure_upload_uses_server_provenance_and_owner_check`
- `backend/tests/test_paper_revisions.py::test_invalid_definition_returns_field_error_and_preserves_saved_draft`
- `TestApplyPaperEvidenceArchivesManualReasonInReviewTransaction`

这些是原实现阶段在独立HEAD与当前候选均复现的旧失败，本轮没有修改、放宽或重新运行它们。完整逐项记录在原checks.json中，实际协作状态仍以本项Issue为准。

## 本轮文档核验

原话按所属目标逐字保留，图像实际读取并比对SHA-256、PNG签名和尺寸；代码/用例按原摘要哈希核对。相对链接、六项映射及原生父子关系由本轮拆分核验记录汇总，见[拆分索引](../213-review-workspace-navigation/README.md)。

## 环境与发布边界

业务实现保持原样，不改标准键、不改数据、不调用模型、不重写提交、不推送或部署。远程Spec尚未核验，Issue继续开放。

## 2026-11-05 当前状态单条跟踪与卡片清理

本轮用户已确认三项需求并授权在旧Issue实施。FR-005～FR-007实际代码、用例、源码摘要和机器结果见[本轮核验](assets/current-status-validation.json)。原上轮失败记录继续保留，不以本轮结果替代。

### 故障反例与定向结果

- 五项前端故障用例在未改生产源码的HEAD归档上全部失败；旧Go接口因没有当前workflow_status而使新增生命周期用例失败。修复后本轮详情／列表定向13项通过，Go九项通过。
- Go用真实SQLite插入与HTTP读取覆盖管理员、超级管理员的拒绝→送审→再次拒绝→送审→批准，检查列表与待检查互斥、状态筛选、分页、无交接存量兼容、非管理员拒绝访问及内部审核事件保留。
- 相邻前端合计52通过、7失败；独立未修改HEAD基线复现相同七项，失败名称和首条错误完全一致。旧测试中依赖已删除摘要卡片的重复材料名计数、关键词展示已按用户新要求调整；其他旧断言保持。
- 七项基线失败：材料状态分类区旧断言、单臂压强旧投影、物性数值类型、旧“我的论文”入口、旧列表请求参数、旧空态文案、跨来源物性条件显示。逐项完整名称与错误见机器核验。

### 必需质量门

隔离HEAD归档只覆盖本次明确文件，不引入并发后端修改。完整表单契约188通过；变异检查检出八项渲染回退与四项漏红回退；科学字段契约通过；TypeScript及Vite正式构建通过。Go定向九项通过；没有宣称远端CI或全部旧套件通过。

### 真实CaH6只读核验

沿用本机原生实时开发环境读取127.0.0.1:8080，既有文件监听已自动加载Go改动。没有执行服务启停、迁移、回填、提交或审核操作。论文1208仍保留旧批准版；待检查查询返回一条pending，已检查和已拒绝筛选均为零条，内部原审核事件保留。

以隔离正式构建连接本机真实只读API，六组浏览器核验覆盖管理员／超级管理员检查列表、上传者1440与390宽详情、超级管理员详情、公开访客详情，并检查英文切换。有权限者显示待审核与旧批准版说明；访客只显示公开批准状态；旧卡片消失，各材料化学式仍正常显示；无横向溢出、浏览器异常或写请求。没有自动批准科学数据，不把本次状态与布局核验宣称为重新解析或全篇科学验收。

截图：[桌面详情](assets/current-status-desktop.png)、[窄屏详情](assets/current-status-mobile.png)、[超级管理员待检查](assets/current-status-pending.png)。复查脚本为tests/02_identity_governance/current-review-state-browser.mjs，凭证只由进程环境传入，不归档。

### 文档与边界

已更新本Issue需求、计划、任务、数据模型、契约、使用说明和需求检查，并同步角色、审核及检索详情Overview和导航。本轮没有推送或阿里云／Docker部署；远程Spec双向链接仍未验证，Issue继续开放。
