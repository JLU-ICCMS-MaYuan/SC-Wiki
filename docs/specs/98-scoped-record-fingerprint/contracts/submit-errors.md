# 提交错误契约

HTTP 409 保留外层 `scientific_data_integrity_error`。当 `uq_property_records_source` 冲突时，`issues[].code` 为 `source_identity_conflict`，范围为 `material_states`。消息明确说明系统生成或保存物性记录身份发生冲突，请联系管理员处理，无需修改已填写的科学数据。

不能仅凭约束名称猜测第一条记录有错，也不能误报 `record_key` 重复。实际模块内的记录键冲突仅比较同一状态、同一模块内的键，属于独立分支。响应不包含 SQL、底层约束原文或驱动信息。

## 旧任务入口

`GET /api/upload-tasks/{task_id}`：任务已清理但正式论文存在时，仅对所有者或已批准管理员返回 HTTP 409、`detail.code=UPLOAD_TASK_SUBMITTED` 和 `detail.paper_id`；消息为“该论文已提交审核，解析任务已归档，请查看论文详情。”。前端导航 `/papers/{paper_id}`，清理本地旧任务选择并刷新任务列表。无权限用户与真正不存在的任务保持原 404，不返回论文 ID。
