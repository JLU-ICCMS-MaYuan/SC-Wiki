# 数据与状态模型

无迁移，无标准科学键变化。
- papers.review_status、content_revision、approved_revision：当前公开科学图资格，保持既有规则。
- PaperHistoryEvent.classification_snapshot.handoff：只投影最新合同头；holder派生workflow_status。不读取整份manuscript_snapshot到列表。
- 私有API新增workflow_status，值为pending/approved/rejected；can_revise由原上传者与author归属共同决定。没有合同的历史稿回落既有rejected规则。
- PaperRevisionDraft与ScientificReviewDraft持有当前修订/审核稿，正式交出后旧写凭证失效，历史快照不改。
- 材料state_key为跳转身份；#编号仅当前展示序号，空间群、化学式和pressure_value_gpa沿现有标准键。
