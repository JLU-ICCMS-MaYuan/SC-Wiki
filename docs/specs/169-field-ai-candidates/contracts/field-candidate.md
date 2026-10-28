# 字段候选契约

字段详情新增 candidate：值、理由、依据、应用资格及服务端令牌；旧候选标 historical。

`POST /api/rag/evidence/field-candidate/prepare` 接收 target、target_id、item_key、candidate_token；服务端校验权限与版本，返回 preparation_id 和 patches，不接受客户端自选候选值。

宿主通过既有 field-draft 接口保存 patches，然后 `POST /api/rag/evidence/field-candidate/finalize` 接收目标、item_key、preparation_id，验证实际保存内容与来源后返回字段详情。

过期／并发返回 409，无权限返回 403，非法类型拒绝。所有候选应用接口零模型调用；确认失败可重试且不误标通过。

字段详情对内容已保存但未完成确认的申请返回 candidate.preparation_id，重开后可直接重试确认，不再次保存或调用模型。已通过内容主动再次核对不要求重复填写人工修改理由；实际新改动仍执行既有说明要求。
