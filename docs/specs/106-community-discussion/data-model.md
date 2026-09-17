# 数据模型

## community_systems

system_key 为主键，保存规范化元素组合；created_at 为首次互动时间。合法体系页可以在尚无讨论行时读取，首次写入幂等建立。公开论文按 chemical_systems 的同名 system_key、当前论文 revision 和 approved 状态聚合，不返回未公开元数据。

## community_entries

字段：id、kind、title、body、author_id、question_id、answer_id、paper_id、system_key、parent_id、reply_to_id、status、created_at、updated_at、activity_at。

| kind | 唯一直接目标 | 说明 |
| --- | --- | --- |
| question | 无 | title 必填，body 可空 |
| answer | question_id | body 必填 |
| comment | answer_id / paper_id / system_key 三选一 | parent_id 指向根评论，reply_to_id 保留具体回复对象 |
| danmaku | paper_id / system_key 二选一 | 纯文本，不可编辑 |

status 为 visible、deleted、hidden。删除和隐藏状态不暴露正文；只有 hidden 可由管理员恢复。问题/答案状态影响全部后代，评论状态保留占位和已有回复但不能继续回复。关联论文、问题、答案的外键物理删除级联，parent/reply_to 删除置空。用户外键不物理删除。

索引覆盖目标、kind、status、id 和问题活跃时间。列表每页默认 20，最大 50。标题 3–200 字，问题/答案正文最多 20000 字，评论 2000 字，弹幕 120 字，举报和处置原因 5–1000 字；按 Unicode 字符计数。

## 点赞、举报、处置与通知

- community_votes：entry_id + user_id 联合主键，仅答案。PUT 幂等添加，DELETE 幂等取消，排序实时聚合。
- community_reports：id、entry_id、reporter_id、reason、status、created_at、resolved_at；同账号同内容只保留一条举报。status 为 pending/resolved。
- community_moderation_events：id、entry_id、actor_id、action、reason、created_at；只追加审计，不允许编辑。
- community_notifications：id、recipient_id、actor_id、entry_id、kind、read_at、created_at；不保存内容正文或论文标题。发布事务内创建，接收者集合去重，过滤自己。读取时重新校验内容和目标权限，失效通知不计入未读数。

账号展示只返回公开用户名、头像和封禁标记；注销账号返回“已注销用户”且不提供资料链接。
