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
