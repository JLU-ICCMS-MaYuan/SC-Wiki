# 右侧栏 UI 与接口契约

唯一功能条款为 spec.md FR-001—021；本文件只登记对应接口职责，不复制功能规则。

入口与字段详情：复用 summary、identify-field、field-detail 及稳定字段归属。
局部写入：复用 draft-state、draft PATCH、manual-context 与 manual 资料接口；当前字段值、理由和附件保存顺序保持。
主动核对：复用 field-input、purpose=field 的任务创建、preparation 与 jobs 状态。后台输入令牌绑定当前字段及资料，不依赖无关全稿修订。
候选：prepare／finalize 与真实人工决定按现有权限、版本及幂等处理。
原页图片：按当前授权文件、来源摘要和可靠位置读取，失败不伪造内容。

侧栏过程上报采用小状态投影；不因 UI 调整扩大其他模型入口的审核范围。当前实现和验证范围见 spec.md 的状态表，不能把本契约存在当成已实现。

## 现有接口的字段范围

- GET field-input：target、target_id、item_key；单字段响应 records 及 field_token。
- POST jobs：target、target_id、purpose=field、retry_keys 只含当前字段、expected_field_token；准备进度使用 progress_id。不是把 summary 的全稿版本当成字段输入令牌。
- GET jobs/{job_id}：id、status、progress、error、completed_batches、total_batches、current_batch，以及可选 activity/activity_log。单字段完成响应会重建当前字段输入令牌，确认持久化结果存在后才返回当前字段结果；job completed 不等于科学 supported。
- PATCH draft：target、target_id、expected_version、changes；侧栏局部保存使用 field_scope。宿主只推进实际保存部分的基线，无变化不请求。
- GET manual-context：当前 target／target_id／item_key 及 field_scope，返回本字段人工资料保存所需版本；它与模型 field_token 语义不同。
- PUT manual：expected_version、reason、no_evidence_reason、text_items、changed_fields；files 上传沿现有 expected_version 与 file。写入阶段及失败不能合并成虚假的全部保存成功。

activity 包含 stage/message 及可选 tool/file_id/page/summary；文本限长，activity_log 最多12条。仅传真实公开阶段、工具动作和模型声明的简短摘要，不传模型隐藏逐字推理、原始流、提示词或凭据。工作进程只在 purpose=field 接入上报，模型调用次数不增加。更新只读取控制键并检查 owner/status，终态与取消后拒绝迟到进度。

这些字段来自当前 evidence API、fieldDrafts、review_progress 和 ManualEvidenceSection。科学通过、候选及来源持久化继续使用原契约；小投影不能赋予核对资格。

PDF正文每份最多100,000字符，沿现有人工附件输入传入当前字段核对；成功模型调用的读取回执和科学结论分别表达，不新增标准科学键或API入口。其他文本上限保持20,000字符。
