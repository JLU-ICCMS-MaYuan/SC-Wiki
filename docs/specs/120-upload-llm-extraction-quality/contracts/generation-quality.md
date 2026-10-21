# 接口契约：按需生成与诊断

`GET/PUT /api/rag/upload-tasks/{task_id}/draft` 保留已有正式字段，在响应增加 `generation_issues[]`。代码稳定值为 `main_unread|source_absent|model_missing|quote_unlocated|invalid_format|candidate_missing|conflict`；每项包含 `field`、非敏感中文/英文本地化消息与当前值/来源版本哈希。客户端不能通过 PUT 为新值伪造 AI 通过状态。

首次合格字段直接使用；缺项或无效字段最多一次定向生成请求。第二候选只有满足同源、有效证据和非冲突的严格改进才能替换；两者无法判优时保留首值并返回 `conflict`，需要人工核对，不能视为 `supported`。数字事实统一来自已验证候选，不接受汇总或建议直接覆盖非空值。

来源核对与 #109 保持现有 `item_key/content_hash/source_hash` 绑定。角色或文件哈希改变时旧结果过期。私有尝试产物只面向任务所有者/管理员，公开任务状态只返回阶段、计数、错误摘要，不返回原文或凭据。
