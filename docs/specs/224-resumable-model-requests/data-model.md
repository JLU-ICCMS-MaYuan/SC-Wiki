# 数据模型

- task.model_execution：generation、status、输入摘要、草稿摘要、heartbeat；公开DTO仅暴露状态/安全活动，不暴露内部路径和凭据。
- 任务产物model-runtime/<输入摘要>/calls/<请求摘要>-<序号>.json：完整请求、必要图片来源、模型安全身份、response、completed。原子写入并复读；结果提交与执行代次检查串行。
- memory：旧过程滚动摘要及已总结消息身份，原始history另存；固定科学依据不进入摘要替代路径。
- model_activity：当前phase、attempt、started_at、receiving、retry_at、脱敏error、request_id及有界公开历史。完整失败独立归档。
- paused/pausing：cleanup_at为空，用户主动清理才删除；活动上限仍包含。正式提交后沿既有正式数据所有权。
- 模型配置仅保存provider/model/catalog_id等安全引用；恢复重新解析当前配置，不把密钥写入产物。
