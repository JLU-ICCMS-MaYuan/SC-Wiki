# 数据模型：流程元数据

- 上传状态：`workflow_policy=typed-parsing-v1`、`workflow_assessment`（结论、理由、来源、通用题录、来源摘要、模型和窗口覆盖）、匹配后才生成的 `_parsing_workflow`。
- 绑定：`workflow_key`、`workflow_version`、`form_key`、`form_version`、`form_sha256`。由程序登记创建，不属于标准科学字段，不允许模型或客户端改写。
- `needs_workflow`：`processing_status=needs_input`，保留通用结果，无可编辑科学表单，不自动轮询，不表示全部解析完成；生命周期沿现有活动清理规则。
- 匹配：选择并绑定→专用处理→ready/failed；判断失败停在needs_workflow，文件读取失败为failed。
- 草稿、工作稿、正式提交元数据及整稿快照保留绑定。正式读取从提交元数据恢复，不根据当前分类猜身份。
- 历史缺失绑定沿原路径读取，不自动迁移；带新策略的任务缺失绑定不得执行专用操作。
