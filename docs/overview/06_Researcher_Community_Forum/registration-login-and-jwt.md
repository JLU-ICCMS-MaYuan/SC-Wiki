# 注册、登录与 JWT

## 功能说明

通过邮箱、密码和唯一公开用户名创建用户，邮箱验证成功后自动登录并签发 JWT，为受保护 API 提供当前用户身份。

## 当前行为

- Go API `POST /api/auth/register` 要求邮箱、至少 10 位密码和全站唯一的 `username`，实名可以省略；注册固定创建 `user`，不再接受管理员角色申请，兼容字段 `is_approved` 直接为 true。
- 用户主动选择的 `username` 为 3–32 位，以字母开头且只含字母、数字和下划线；保留名称及 `sc_` 前缀不区分大小写禁止使用，普通用户名唯一性区分大小写。
- 匿名接口 `GET /api/auth/username-availability` 提供失焦可用性提示，注册最终写入仍由数据库唯一索引处理并发冲突。
- 新账号写入 `is_email_verified=false`，发送验证码成功后返回 202 并进入验证页；验证成功后标记已验证、自动登录并进入用户中心。网易配置示例使用 `sc_wiki@163.com` 发信。
- `POST /api/auth/verify-email` 验证 6 位码并签发会话；验证码有效 5 分钟、单次消费、最多错误 5 次。重发需要本次注册密码（仅保留在弹窗内存），未知邮箱和错误密码统一拒绝；重发受 60 秒冷却、邮箱/IP 每小时 5 次和 UTC 每天 10 次发送尝试限制。新码发送成功后替换旧码并清零尝试次数。
- Go API `POST /api/auth/login` 只接受邮箱和密码，要求 `account_status=active` 且邮箱已验证，返回 JWT、用户名、角色和一次更名资格，不返回实名。
- 用户写入失败时，只有 MySQL `1062` 唯一键冲突返回“邮箱或用户名已被占用”；其他数据库错误返回“注册失败”并记录服务端错误。
- 历史账号迁移后获得 `sc_` 加 12 位安全随机字符的临时用户名，可通过 `PATCH /api/auth/username` 成功自行更名一次；失败不消耗资格。
- 前端 `AuthContext` 将 token 和不含实名的用户信息保存到 `localStorage`，启动时通过 `GET /api/auth/me` 刷新服务端身份；通用 API 客户端自动附加 `Authorization: Bearer`。
- JWT 包含 `session_version`。Go 和 Python 权限解析都会校验数据库中的账号状态与会话版本；改密、封禁、注销或角色变化会递增版本，使旧 JWT 立即失效。

## 工作流程

用户提交注册资料后，服务创建未验证账号并发信；验证成功后前端保存 JWT 并进入用户中心。首次发信失败不会删除账号；用正确密码登录后可继续验证或重发，失败时不会声称已发信。后续上传、用户中心和工作台请求携带 token；中间件同时验证签名、会话版本、账号状态和角色。

## 约束

- JWT 使用 HS256，Go 服务要求 `JWT_SECRET_KEY` 存在。
- 未验证邮箱登录返回 `403/email_not_verified`，前端提供继续验证入口；封禁/注销账号不能登录或通过验证码签发会话。历史已验证账号不重新验证。
- `users.username` 使用 `ascii_bin` 唯一索引，允许 `Alice` 与 `alice` 共存并拒绝完全相同的重复值。
- 邮箱不进入公开资料 DTO；真实姓名由用户选择填写，填写后会在公开研究身份页展示。
- 注册验证依赖 SMTP 与 Redis；配置缺失或发送失败明确报错。SMTP 使用 TLS，总 IO 期限为 20 秒；验证码只以 HMAC 摘要保存，不在生产日志打印。

## 代码与测试

- `goserver/handlers/auth.go`
- `goserver/handlers/username.go`
- `goserver/middleware/auth.go`
- `goserver/handlers/username_test.go`
- `frontend/src/context/AuthContext.tsx`
- `frontend/src/components/AuthDialog.tsx`
- `frontend/src/components/UsernameField.tsx`
- `backend/username_policy.py`
- `backend/security.py`
- `alembic/versions/20260824_0009_add_account_identity_governance.py`
- `alembic/versions/20260821_0006_add_public_usernames.py`
- `tests/test_username_policy.py`
- `tests/07_researcher_community_forum/test_issue31_public_username.py`

## 相关变更记录

- [Feature #31：唯一公开用户名与贡献榜身份](../../specs/31-community-ranking-visuals/spec.md)
- [GitHub Issue #31](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/31)

## 已知问题

- 当前未提供忘记密码或邮箱变更流程。
- 网易真实收信与目标环境完整注册流程仍待私密配置后的验收；自动化测试不证明外部投递。
