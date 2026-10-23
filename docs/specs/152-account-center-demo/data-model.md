# 正式数据与状态

## 资料与贡献

- User：复用姓名、机构、ORCID、研究方向、头像和邮箱。编辑草稿只在组件内存，保存继续使用原 PATCH 接口。
- Paper：收录列表保持 uploaded_by_user_id 归属；搜索和分页不改变数据。
- PaperHistoryEvent：筛选当前用户的 reviewed 事件，每论文取 occurred_at 最大值，时间相同时取 id 最大值。checked_status/checked_at 表示本人历史；paper.review_status 是当前论文状态。
- 不增加数据库表或迁移，不补造未知历史。

## 改密验证

- 作用域：`password-change:<user-id>:<session-version>:<email-hash>`；Redis `verify:code:` 与 `verify:attempts:` 使用该作用域，与注册邮箱 key 分开。
- 存储内容：随机验证码的 HMAC 摘要，五分钟 TTL，不记录明文密码或验证码。发送额度复用邮箱/IP 限流，身份尝试另限账户/IP 每五分钟二十次。
- 状态：身份待验证 → 邮件发送成功并发布摘要 → 验证码消费 → 数据库事务更新密码与会话版本。发送失败不发布新码；事务失败不恢复已消费码，用户重新获取。
- 并发：保留认证时的会话快照，在数据库行锁内与当前版本比较；仅一个有效消费可以成功。会话版本变化后所有旧作用域失效。
- 客户端取消清空敏感输入；服务端验证码仍按 TTL 和用途约束，界面取消不等于撤销其他会话中的有效操作。
