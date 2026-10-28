# 数据与状态

- `UploadDraft.paper.knowledge_graph_title`：可选、可空字符串，独立于 `title`；数据库既有字段 `papers.knowledge_graph_title` 为可空 VARCHAR(200)。不增加列、不改变生成或存储约定。
- 表单读取：字符串原样显示，null 或缺失显示空文本；单纯打开页面不补写数据。
- 编辑：通过 `setPaperField` 写当前草稿，通知对应字段核对失效；保存器将变化发送到 `['paper', 'knowledge_graph_title']`，使用既有 before 与 expected_version 防止覆盖。
- 保存成功：更新本地保存基线，重载读取保存后的草稿；失败保留未保存编辑并显示错误，不伪造成功。
- 来源核对：`paper.knowledge_graph_title` 绑定已有核对记录；值变化按现有内容指纹规则使旧结论失效，历史保留，无自动人工确认。
