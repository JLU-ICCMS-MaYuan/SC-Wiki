# 数据模型

复用审核记录 JSON 的 `field_candidate`：id、values、explanation、evidences、basis_kind、content_hash、source_hash、review_started_at。仅服务端从显式主动核对的真实结果产生。

准备记录保存在原审核行 resolutions 的用户条目：preparation_id、候选快照、原版本、预期新字段内容与来源、稳定身份补丁。准备阶段不授予通过。

确认后新审核结果保存 `field_decision`（field-review-v2、approve、操作者、时间、内容与来源版本）、候选理由与依据、`applied_candidate` 和审计事件；原值历史保留。重复确认幂等。

字段详情按当前字段和用户查找已准备且预期内容已保存的申请，以 `preparation_id` 恢复中断确认；不扫描其他字段的候选。较晚人工决定或新候选使旧申请失效。
