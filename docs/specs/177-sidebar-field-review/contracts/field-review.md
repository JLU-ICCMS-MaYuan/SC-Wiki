# 单字段核对契约

新字段准备入口返回当前唯一字段及 field-input-v1 签名。purpose=field 新请求携带稳定 item_key 和字段签名，不携带 expected_draft_version。旧入口继续原协议，不把旧版本串解释为新令牌。

实现接口：GET /api/rag/evidence/field-input 接收 target、target_id、item_key，返回一个 records 项和 field_token。POST /jobs 使用 purpose=field、retry_keys=[唯一字段键]、expected_field_token；完成后的 GET /jobs/{id} 再核验当前字段并只返回已持久化的该字段。令牌为内容指纹，权限仍由原认证和目标授权负责。

PATCH /draft 的 field_scope=true 使用每个稳定路径的 before 比较，不因无关整篇版本变化失败；默认请求仍检查 expected_version。manual-context 的 field_scope=true 返回 manual-field-v1 版本，对应理由／文件写入校验当前字段与原文；模型任务输入令牌另包含当前人工依据内容，真实理由／附件变化会撤销旧任务资格。

启动及完成重建该字段并核验签名；全局版本变化不拒绝。人工依据保存需等待值保存，字段准备需等待人工依据全部保存。

返回仅当前字段；候选仍须显式应用。完成后的同字段输入结果可读取复用，其他记录零写入。过期当前值／证据、删除、无权限和取消维持明确错误。
