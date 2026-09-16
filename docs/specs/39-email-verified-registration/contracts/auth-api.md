# 邮箱验证认证 API

## `POST /api/auth/register`

输入：`email`、`username`、`password`、可选 `real_name`。不接受角色或管理员申请字段。

成功：`202`，返回 `requires_email_verification=true`、规范化后的掩码邮箱和 `resend_after_seconds=60`。

错误：`400` 校验失败，`409` 邮箱/用户名冲突，`429` 超额，`503` 邮件或限流服务不可用。

## `POST /api/auth/verify-email`

输入：`email`、`code`。

成功：`200`，返回 `access_token`、`token_type='bearer'`、`user`；验证码原子消费。

错误：`400` 统一表示无效、过期或已消费；`429` 表示尝试次数或额度达到上限。

## `POST /api/auth/resend-verification`

输入：`email`、`password`（注册时设置的密码）。

成功：`202`，凭据正确后返回统一发送提示；已验证或不可用账号不再发信。未知邮箱或错误密码统一返回 `401/invalid_credentials`。

错误：`429` 带 `Retry-After`；`503` 表示邮件或限流服务不可用。

## `POST /api/auth/login`

保持邮箱和密码登录。未验证邮箱返回 `403`、稳定错误码 `email_not_verified`，不得复用管理员资格或账号封禁文案。

## 恢复与失败契约补充

- 注册发送失败：503，`code=verification_send_failed`、`requires_email_verification=true`，账号保留但不可登录；响应不声称已发信。额度限制返回 429 和真实 `Retry-After`，同样允许继续验证。
- 未验证账号密码正确的登录：403，`code=email_not_verified`；前端进入继续验证步骤，可填写已收到的码或重发。
- 所有发送限流：429、`code=verification_rate_limited`、`Retry-After` 及 `resend_after_seconds`。
- 验证错误或过期/重放：400、`code=invalid_verification_code`；第 5 次错误返回 429、`code=verification_attempts_exceeded`。
- 重发先执行统一配置与配额检查，再校验密码；未知邮箱和错误密码执行相同成本密码比较并返回 401。正确凭据下，已验证或不可用账号返回统一 202，不发邮件。
- 已封禁或注销账号不允许通过验证签发 token。
