# 返修接口契约

前缀 `/api/rag/papers/{paper_id}/revision-draft`。均需登录，上传者身份由认证取得。

- `POST`：创建或恢复草稿。仅 rejected 原上传者。返回 ok、data（共享 UploadDraft）、revision_id、draft_version、base_revision、review_comment、warnings、conflict。
- `GET`：读取已有草稿；不存在返回 404。不得创建草稿。
- `PUT`：输入 draft、revision_id、draft_version；可另带 evidence_preparation_id。返回同一响应结构与新草稿版本；草稿只做结构性验证，提交做完整验证。
- `POST /submit`：输入 revision_id、draft_version、evidence_job_id、expected_evidence_version；返回 ok、paper_id、review_status、content_revision。相同 revision_id 的已成功请求从历史返回成功，不重复升版。
- `POST /structure-candidates`：multipart 的 material_state_index、revision_id、file；复用结构候选解析与来源登记，候选随下次保存落入草稿。
- `POST /api/rag/evidence/*`：目标增加 `{target: revision, target_id: revision_id}`，复用现有核对、建议准备与完成接口。
- Go 论文详情及我的论文响应增加 can_revise。它只控制返修入口，不能用现有 can_edit 代替。

错误：未登录 401/现有认证契约，非上传者 403，不存在 404，状态变化/正式内容变化/草稿版本变化 409，完整校验失败 400；全部保存失败保留原内容。可恢复提示不返回源文件绝对路径或管理员内部备注。
