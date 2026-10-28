# 接口契约：角色判断与确认

- `GET /api/upload-tasks/{task_id}` 在现有 `files[]` 外返回 `role_assessment`，每文件含原声明、有效角色、非敏感识别依据；`needs_role_review` 时暂停解析。只对任务所有者返回，不暴露原文全文。
- `POST /api/upload-tasks/{task_id}/resolve-roles`：请求 `{"expected_revision":整数,"roles":[{"file_id":"...","role":"main|supplementary|attachment"}]}`，必须覆盖本任务全部文件且恰好一个 main。
- 仅状态为 `needs_role_review`、源文件哈希未变且版本匹配时更新；成功返回新任务状态并继续使用已解析文本。重复的同版本内容采用幂等响应；冲突为 409、无权为 403、非法角色为 422。
- 自动纠正高置信错误角色时无额外前端请求，但返回 `role_assessment` 和更新后的 `files[].role`；UI 显示系统判断依据。
- 下游读取采用当前有效角色；来源版本变化使旧字段核对过期。API 不允许在 submitted Paper 上改角色。

## 身份冲突确认

提交返回 consistency_ack_required 时同时返回真实 conflicts 和 consistency_version；message 仅列实际冲突，含双方文件名和值。明确确认请求携带 consistency_acknowledged=true 和 consistency_version；当前文件角色、哈希或冲突改变则拒绝旧令牌并返回新差异。没有冲突时不要求确认。现有字段审核结果和权限保护保持。
