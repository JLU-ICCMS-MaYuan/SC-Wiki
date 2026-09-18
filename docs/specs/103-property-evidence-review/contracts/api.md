# 接口契约

## 统一展示补充

沿用上传草稿、Go 论文编辑及 Python 科学保存入口。关系编辑保持 material_relations 数组内的来源属性，Go 论文文本列请求按现有 JSON 字符串契约序列化。研究材料从保存的材料状态汇总，加载不触发写入。矩阵与原子表是当前结构文本的只读解析结果，不新增写接口、不改变批准权限。

共享前缀为 `/api/rag/evidence`。所有接口检查当前用户和目标权限；论文目标仅管理员可用，禁止自审。

| 接口 | 输入和行为 |
| --- | --- |
| `POST /preflight` | `target`（upload/paper）、`target_id`；从 MySQL 返回 `version`、`needs_check`、`records`、`sources`，不调用模型，不依赖 Redis 任务存活 |
| `POST /jobs` | 上述目标和必填 `expected_version`；返回 `id`、`version`、`status`、`timeout_seconds=1800`。默认复用所有有效结果，包括 missing；显式 `retry_keys` 仅重查指定项和派生依赖 |
| `GET /jobs/{id}` | 运行状态、真实批次进度和错误；完成时返回完整当前项列表，未核对项目保持 unchecked，不能据此自动批准 |
| `DELETE /jobs/{id}` | 仅所有者可取消；停止后续批次及自动续提，保留此前已持久保存的结果 |
| `POST /resolutions` | 目标、`expected_version`、按 key 的 `resolutions`；按审核员分别保存当前版本裁决草稿，每条最多 4000 字，不能裁决旧版本 |
| `POST /prepare-review` | Go 只读准备：`paper_id`、可选 `job_id`、`expected_version`、`resolutions`、实际批准分类 `classifications`；验证全量科学项和内容版本，不执行批准 |
| `POST /jobs/{id}/save-draft` | 旧调用兼容入口，复用后台的持久保存与自动补证逻辑；仅完成的上传任务可用，浏览器无需调用此接口才能保存结果 |

核对项保留 `key/field/label/status/reason/evidences/model`，增加稳定 `item_key`、`fields`、`suggestion`、`current_value`、`source_kind`、`provenance`、`resolution`、`stale`。`key` 用于当前请求，`item_key` 用于跨保存、排序和上传转待审关联；`field/fields` 是当前表单位置。多个受影响子字段可同时标记。

来源类型包括 `paper_quote`、`contributor_structure`、`derived`、`human_review` 和 `unknown`。引句保留文件身份、文件名、原文切片、页码范围及逐字引句；附件来源保存认证提交者、原始内容、文件名、内容摘要与解析依据。派生来源保存输入、规则和程序复核结果，不伪造论文引句。结构来源未知时，整篇审核意见不能直接放行；管理员须按下文 v4 契约保存绑定当前版本的逐条人工决定，且不得伪造原始提供者。

任务进度包括 `completed_batches`、`total_batches`、`current_batch`。按最多八项与来源组组合分批；一组响应校验完成后才递增完成计数。每组科学项扫描完全部原文后保存 MySQL 检查点，后续批次失败不丢失之前结果。排队总量未知时显示动态等待条；等待计时不是进度估算。

`candidates` 保留旧接口兼容并执行严格原文定位，现行页面不发送该参数，也不要求用户选择片段或编辑引句。预检查不会自动创建任务。离页只停止浏览器续提，后台继续保存；用户明确点击取消则停止后续任务处理。

上传使用 `POST /api/rag/upload-tasks/{task_id}/submit`，审核使用 `POST /api/admin/papers/{id}/review`。两者携带 `evidence_job_id/expected_evidence_version`，审核另含 `evidence_resolutions`。缺失参数仍执行全量服务端检查。编辑页必须先完成保存，再读取实际落库内容启动核对。批准请求不能夹带与已保存内容不同的分类。

Go 原 `review_request_id` 保证审核幂等；上传由任务身份和唯一 `upload_task_id` 保证幂等。批准事务保存正式证据、通用科学来源、审核历史，再删除临时核对项；任何一步失败全部回滚。历史事件包含 AI 判断及逐条人工决定。预检查可从同版本永久来源恢复已批准内容。

主要错误包括 `evidence_check_required`、`evidence_missing`、`evidence_review_required`、`evidence_stale`、`evidence_resolution_invalid`。模型配置、响应格式、服务和超时分别返回对应错误；Go 无法访问 Python 时返回 `evidence_service_unavailable`。错误均不自动批准，也不伪装成科学值已核实。

## 建议接口（v3）

- POST /proposals：目标、expected_version、key、values、accepted、reason。验证目标权限/类型/来源，按用户保存编辑草稿；accepted=false 撤销，不改科学数据。
- POST /proposals/prepare：目标、expected_version；返回当前用户已接受的稳定字段补丁及申请标识，校验版本与来源，不写科学数据。
- POST /proposals/finalize：目标、申请标识；科学数据通过原保存接口成功后，精确验证实际断言、来源与候选，绑定人工结果，不调用模型。失败保留待处理草稿。
- preflight 返回 proposal、proposal_draft、decision，仍只读不调模型。prepare-review 继续全量验证权限、自审、来源和最终版本。

建议类型与原字段一致，枚举沿用域规则；结构只确认来源，不提供生成式替换。人工手改不冒充 AI supported；仍存疑需理由。旧结果只读兼容，不在刷新时升级任务。

分阶段保存补充：`/proposals/prepare` 返回 `preparation_id`、`patches`、`resume_stage`（可选 scientific/finalize）。既有论文、科学草稿及上传草稿保存请求携带 `evidence_preparation_id`。Go 在论文行锁内调用只读 `POST /proposals/validate-save`（目标、申请标识、stage=paper），Python 科学保存在同事务内检查 scientific 阶段预期版本；上传保存共用任务锁。保存部分成功时准备接口识别精确中间状态，重试跳过已完成阶段。finalize 对同用户、同实际内容的重复申请幂等。

## v4 人工裁决与未核对草稿

/proposals 允许为当前项创建 unchecked 草稿并保存 values/reason。accepted=true 且目标 paper 可由有权限管理员填写非空理由确认无直接原文或未核对内容；upload 仍要求完成来源核对。返回 draft 与版本，按用户隔离。prepare/finalize 校验权限、类型、依赖和实际值，生成 human_confirmed、actor_user_id、reason、accepted、final_content_hash、source_hash 等决定字段。preflight 返回人工来源类型 human_review 及原 AI 判断，未核对草稿保持 unchecked。后台只重查未完成 AI 项，不将草稿占位视为有效模型结果。Go 仅接受 Python 准备的版本绑定人工决定，不接受单靠批准请求附带的任意理由绕过核对。

## 编辑当前值后的人工确认

管理员编辑页接入共享流程的可选 getCurrentValue/saveCurrent 回调，当前值与聚焦位置按稳定身份读取。未保存编辑的新理由不请求旧 expected_version；完成依次调用原论文/科学保存接口、preflight、proposals（当前版本、accepted=true、手改后 values={}）。任一步失败保留当前输入并允许重试，不调用 jobs 或 review；正式批准仍须用户另行提交。

普通保存刷新 preflight，保留尚未提交的新理由；编辑序号与目标身份隔离迟到响应。stale 表示旧判断仅供参考，不禁用管理员的新理由。preflight 不公开过期候选、决定或接受草稿；清空后不返回已删除压强项。重新查找先保存成功，再预检查与创建模型任务。接口与数据库字段不增加，previous_review 仅扩展已有草稿 JSON 的审计内容。

## 材料名、空化学式与字段错误

上传草稿和 `PUT /api/rag/papers/{id}/scientific-draft` 接受 `material_states[].material_name`（可空字符串，最多 255 字符）。材料名和 material 至少一项非空；否则 HTTP 400、code=state_material_required、field=material_states[i].material_name。非法非空公式返回 400、code=invalid_chemical_formula 并定位 material；类型/长度错误也返回明确字段。详情和导出保留独立名称与空公式，不能用旧嵌套实体或 state_key 回填公式。

preflight 的名称断言和相关上下文遵循相同稳定身份与版本规则。保存后已经删除的字段不再是人工确认或重新查找目标；抽屉关闭后可分别确认仍存在的名称。搜索额外返回 material_name；formula 字段仍为真实公式，化学式无匹配不放宽查询。见 [保存验收](../material-name-save-flow.md)。
