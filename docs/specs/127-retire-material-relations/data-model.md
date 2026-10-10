# 数据清理设计

## 专列与嵌入值

- `papers.material_relations`：删除专列；模型和 API 不再映射。
- `scientific_upload_drafts.draft`、`paper_revision_drafts.draft`、有效 Redis 草稿及 `review_artifacts`：删除 `paper.material_relations` 和分段顶层 `material_relations`，保留同级其他键。
- `scientific_evidence_checks`、`scientific_evidence_sources`：删除字段身份为 `paper.material_relations` 的独立项；其他项保留。
- `paper_history_events.classification_snapshot` 及其他审核/人工历史 JSON：只删除材料关系字段或专属项，保留事件、身份、时间与其他决定。
- 受影响的 Qdrant 科学来源片段按当前正式来源重建，不能保留退役字段的已发布内容。
- Neo4j：删除所有 `STUDIES` 边及 `Paper.material_relations` 属性；不删除无关材料或论文节点。

## 迁移及重放

升级清理不可恢复。降级仅重建值为空的列，不能复原旧值。新上传提取、旧缓存重放、草稿保存与旧 API 请求均不得再次产生材料关系。
