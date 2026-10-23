# 正式接口契约

- `GET/PATCH /api/account/profile` 的 research_interests 始终返回数组；SQL NULL、JSON null 均序列化为 `[]`，不变更数据库。前端兼容旧服务的 null／缺失字段，显示未填写且能正常编辑。

- `POST /api/account/password-change-code`：登录必需，current_password/email 必须匹配本人；202 返回 resend_after_seconds=60、expires_in_seconds=300，不返回验证码。
- `POST /api/account/change-password`：current_password/email/code/new_password 必填，六位数字验证码，新密码 10–72 字节；204 后所有旧登录会话失效。
- SMTP/Redis 故障拒绝；429 返回等待时间；最多五次错误验证码；用途、账户、邮箱、会话版本隔离，成功消费不可重放。
- `GET /api/account/reviewed-papers`：仅 admin/superadmin，本人 reviewed 历史去重，items/total，checked_status/checked_at 表示本人检查而非论文当前状态；支持 keyword/review_status/limit/offset。
- 收录使用现有 my-uploads，保持上传归属并补筛选分页。
- `/superadmin?section=users|applications|charts|news|models|audit|papers`、`/admin?section=papers`，新标签页直达；沿用真实鉴权。
- 不发送未经授权的实际验收邮件；本地 SMTP 测试及真实外部邮箱投递分开记载。
