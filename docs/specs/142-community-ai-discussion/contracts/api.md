# API 契约

所有新写接口位于 /api/community/ai，要求正常且验证邮箱的超级管理员。POST /questions 接受 request_id/title/body；POST /questions/generate 接受 request_id；返回批次 ID 和已知问题 ID（202）。同请求 ID 同参数复用，异参数 409。

GET /batches 返回超级管理员最近批次；GET /batches/{id} 返回进度和任务安全元数据；POST /batches/{id}/retry 重试失败的选题或检索；POST /tasks/{id}/retry 按模型重试或重生成。GET /entries/{id}/revisions 返回超级管理员修订历史。公开进度通过 Go 问题 DTO 的 generation_tasks 返回，不公开批次凭据、发起人或内部错误。

Go 旧 POST /entries、DELETE /entries/{id}、PUT/DELETE vote、POST reports 拒绝 403 community_read_only。PATCH /entries/{id} 仅超级管理员编辑答案，必填 revision/body；问题、评论不可改。moderate 要求 revision/action/reason，仅超级管理员；变更冲突 409 community_revision_conflict。新增超级管理员内容管理列表提供隐藏内容的恢复入口。

没有模型、缺失迁移或 Redis 不可用给出明确可恢复错误；无认证 401、非超级管理员 403；隐藏内容公开不可读。公开 AI 答案附模型元数据、来源、修订标记及版本；不公开端点和密钥。
