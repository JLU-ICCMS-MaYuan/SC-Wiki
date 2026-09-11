# 数据模型

新增 property_evidence_checks：自增 ID、paper_id/revision、record_id、内容摘要、来源摘要、规则版本、结果 supported/uncertain/unsupported、原因、模型、证据快照、创建时间。按记录与摘要复用，删除论文时清理。不改变 source_fingerprint。

Redis 任务：随机 ID、owner、upload/paper 目标与 ID、目标摘要、记录、来源、状态、进度、结果与错误。queued → running → completed/failed/cancelled。TTL 复用上传配置，凭据仅短期 Redis 存储并在终态清理。取消通过 WATCH 防止被工作进程的完成写入覆盖。

`evidence-cache:{owner}:{target}:{target_id}:{version}` 指向尚未应用或已应用的已完成任务；读取仍验证归属、状态及版本。失败和取消任务不提供可复用结果。正式核对缓存按 record_id、content_hash、source_hash、rule_version 查询；材料状态、物性值、条件、相关结构或来源变化后失效。

数据库 `record_id` 外键随 `property_records` 删除级联清理；不为不存在的记录保留核对缓存。迁移 `20260911_0103` 仅新增表和索引，不批量回填历史证据。上传在同一事务里用落库后正式记录摘要保存核对结果。

审核事件增加逐条裁决快照：记录、证据、模型结论、人工理由；审核员与时间复用原事件。无有效出处不允许人工绕过。
