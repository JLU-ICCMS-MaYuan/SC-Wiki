# 接口契约

/api/community/ai/models 仅超级管理员获取安全模型选择信息；POST /questions/{id}/answers 接受 request_id/model_key，返回已排队请求；GET /questions/{id}/queue 返回题内队列；POST /answer-requests/{id}/retry 接受新 request_id 并复制模型至队尾。

PATCH /turns/{id} 接受 body/revision，保留旧段修订；GET /turns/{id}/revisions 返回历史。所有写入要求正常且验证邮箱的超级管理员。旧 /tasks/{id}/retry 拒绝 workflow_changed。

Go 问题 DTO 增加 model_count/response_count；答案 DTO 增加 turns（首答+追加），每段含稳定 key、正文、来源、序号、版本、回应引用及可见性。回应 key 为 A{entry} 或 A{entry}T{turn}。模型选择不返回 endpoint/key。

隐藏/缺失问题404，权限403，UUID异参数409，前文变更 generation_conflict，过长 context_too_long；实际入队后失败保留记录且继续。

POST /api/community/ai/questions/{id}/answers/batch 接受 request_id 与 model_keys（非空、不重复、有序）；返回 request_id/items。全部校验通过才写入，否则无任何子任务。旧单模型接口保留，批量/单次UUID不可跨用产生歧义。

GET /api/community/questions/{questionId}/answers/{id} 为公开独立答案页数据入口，同时校验答案类型、question_id和既有祖先可见性。前端路由 /share/discussions/:id/answers/:answerId；回应锚点 #answer-A...。
