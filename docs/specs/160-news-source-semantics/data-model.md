# 收录前候选数据模型

新增 news_feed_candidates，仅服务资讯采集和模型判断，不与正式科研表关联。

| 字段 | 含义 |
| --- | --- |
| key | DOI优先、无DOI用规范化URL的SHA256稳定身份 |
| record_json | 规范化Record与多来源身份/链接；包含内部摘要及关键词；MySQL使用MEDIUMTEXT |
| content_hash | 模型实际输入title/abstract/keywords的指纹 |
| rule_version | 当前相关性规则版本 |
| status | pending、running、related、unrelated、insufficient、failed |
| model、reason | 本次模型与中文判断依据，包含原文引用或安全异常类型 |
| attempts、attempt_token | 已领取尝试次数与防止过期任务写回的标识 |
| first_seen_at、last_seen_at、updated_at | 首次发现、最近发现、内容/状态更新时间，UTC秒精度 |

status有数据库枚举约束，status/updated_at建立索引。没有新增公共API字段。只有related在写回事务中调用既有upsert，候选结果和公开记录一起提交；失败则共同回滚。重复采集同一内容不刷新updated_at，保留待判顺序；内容或规则变化重置尝试次数。不同DOI不按题名合并，缺少日期不伪造发表日。

新迁移20261102_0160合并两个已提交基线头20261020_0049/20261101_0198并创建候选表，降级仅删除该表。2026-11-02 已按用户明确授权在本机原生 `127.0.0.1:3307/scwiki` 执行，与已执行的20261102_0204并列保留两个真实迁移头；未修改旧迁移或重跑科学表单迁移。没有回填或追溯删除旧公开资讯。备份、隔离恢复及逐表验证见 [本机迁移验收](local-migration-validation.md)。
