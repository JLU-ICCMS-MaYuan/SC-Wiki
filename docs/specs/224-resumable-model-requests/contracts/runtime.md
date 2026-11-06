# 接口契约

- POST /api/upload-tasks/{task_id}/pause：仅所有者；运行/排队任务设置pausing并提升generation；重复停止幂等。已成功或送审拒绝停止。
- POST /api/upload-tasks/{task_id}/resume：仅所有者；paused或服务中断的可恢复任务；任务锁串行、版本一致、仅排队一次，响应202。不可用配置/变更返回明确409，不隐式换模型。
- GET /api/upload-tasks/{task_id}/parsing：新增model_activity/model_execution安全状态；暂停和终态停止高频轮询，pausing保持轮询。
- 原cancel保留放弃任务语义。显式清理可清理paused，运行/pausing仍受保护。
- 错误仅公开允许字段：HTTP状态、稳定类型、脱敏message、request_id、output_started；不公开header/body全文、密钥、原始工具参数或内部思维链。

- GET /api/upload-tasks/{task_id}/model-activity?before=<时间戳>&limit=100：沿任务读取权限分页查看完整安全过程日志，用户主动触发；不读取或公开原始模型请求和凭据。
