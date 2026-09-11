# 接口契约

`/api/rag/evidence` 下 `POST /preflight` 与 `/jobs` 接受 target（upload/paper）、target_id，jobs 必须 expected_version。

| 接口 | 返回与约束 |
| --- | --- |
| `POST /preflight` | version、needs_check、records、sources、可复用的 job_id；不调用模型 |
| `POST /jobs` | id、version、status；可携带以记录 key 为键的 candidates 多证据数组，手动原文仍须在当前来源唯一定位 |
| `GET /jobs/{id}` | id、status、progress、error；completed 时返回 records，包含 key、field、label、status、reason、evidences 与 model |
| `DELETE /jobs/{id}` | status=cancelled；只允许任务所有者操作，取消不应用候选 |

记录 key 在上传时为材料状态序号/模块键/记录键，在正式论文中为记录主键；field 提供具体记录路径。
证据含文件、片段、页码范围和原文引句。定位失败返回具体原因及记录字段；无有效出处的结果为 missing，不能人工绕过。

POST /prepare-review 为 Go 的只读准备接口，接受 paper_id、job_id、expected_version、逐条人工理由；验证管理员、自审、任务归属和当前数据库内容。直接调用不修改或批准。

上传 submit 与 Go review 增加 evidence_job_id、expected_evidence_version；review 增加 evidence_resolutions。缺失参数仍执行服务端检查，不能绕过。错误：409 evidence_check_required、evidence_missing、evidence_review_required、evidence_stale；模型配置/服务失败分别返回明确代码。

上传端点为 `POST /api/rag/upload-tasks/{task_id}/submit`，审核为 `POST /api/admin/papers/{id}/review`。
evidence_resolutions 为以正式记录 key 为键的理由映射，每条最多 4000 字；原 review_request_id 负责幂等，
上传由任务身份和数据库唯一 upload_task_id 保证幂等。审核历史响应新增 evidence_review 逐条快照。

模型任务错误码区分 evidence_model_config、evidence_model_timeout、evidence_model_service、
evidence_queue_error 和 evidence_worker_failed；Go 无法访问核对服务时返回 evidence_service_unavailable。
这些错误均保留原操作状态，不解释为用户科学表单填写错误。

任务查询另返回 completed_batches、total_batches、current_batch。排队或旧任务尚未提供计数时为 null；
分组后 completed_batches 从 0 开始，仅在每组模型响应完成且通过结果校验后递增。current_batch 从 1
开始标识正在核对的一组，完成后置 0。前端按完成组数/总组数显示百分比，未知总量使用动态进度条，
等待时间由当前页面独立计时，不作为进度依据。

当前上传及审核界面不发送 candidates，不向用户提供来源选择；由后台自动搜索与选择证据。
原 candidates 参数保留接口兼容及确定性来源校验，不作为用户操作步骤。用户主动重试时，即使预检查有旧疑点
结果，也重新创建任务；后台仅复用已支持记录。人工裁决仍使用已找到的原文与 evidence_resolutions。
