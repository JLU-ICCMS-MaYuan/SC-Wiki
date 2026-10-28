# 表单与保存契约

- 位置：上传校对表单原标题之后，独占一行；窄屏允许辅助说明换行。
- 中文名称：图谱科学标题；英文名称：Knowledge graph title。
- 辅助说明：用于知识图谱节点展示的简短标题。字段：paper.knowledge_graph_title。
- 字段绑定：`data-issue-field="paper.knowledge_graph_title"`，使用 ReviewPaperTextField。
- 值与更新：`draft.paper.knowledge_graph_title ?? ''`；`setPaperField('knowledge_graph_title', value)`。
- 控件状态：readOnly 沿用宿主参数；disabled 为 submitting 或 revision.conflict，与原标题一致。
- 保存使用既有 PATCH `/api/rag/evidence/draft`，只传本字段变化、before 值、target、target_id、expected_version；不另增接口。
- 字段标签打开现有来源核对／字段设置侧栏；侧栏当前值与主表单一致，应用修改使用同一更新回调。
