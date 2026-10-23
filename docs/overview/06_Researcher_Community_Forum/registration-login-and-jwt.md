# 注册、登录与 JWT

## 功能说明

通过邮箱、密码和唯一公开用户名创建用户，邮箱验证成功后自动登录并签发 JWT，为受保护 API 提供当前用户身份。

## 当前行为

- 侧栏和上传页的登录按钮统一进入 /auth，页面在业务侧栏外显示；登录/注册共用邮箱表单，支持中英文、密码显隐和用户名失焦可用性检查。注册字段标签为“用户名 / Username”；重复用户名还会在注册提交时被拒绝，并由数据库唯一索引兜底。
- 登录或注册验证成功优先返回来源路径（保留查询参数与锚点）；无来源时分别进入 /news 与 /account。仅接受安全站内路径，外站、反斜线、控制字符、编码绕过与认证页循环被拒绝。
- 认证页采用紧凑留白和按视口高度调整的动画区域；常见桌面窗口下登录与注册可完整展示，手机/极短窗口及长错误内容仍自然滚动，避免裁剪控件。
- 背景沿用超导圆片与磁轨：无磁场线或屏蔽电流，低温白雾为第四版减量效果；默认 12 秒一圈，推动可加速至 1 秒一圈，点击轨道到点停靠，再推动从 20 秒一圈重启。支持暂停、减少动态和后台冻结。

- Go API `POST /api/auth/register` 要求邮箱、至少 10 位密码和全站唯一的 `username`，实名可以省略；注册固定创建 `user`，不再接受管理员角色申请，兼容字段 `is_approved` 直接为 true。
- 用户主动选择的 `username` 为 3–32 位，以字母开头且只含字母、数字和下划线；保留名称及 `sc_` 前缀不区分大小写禁止使用，普通用户名唯一性区分大小写。
- 匿名接口 `GET /api/auth/username-availability` 提供失焦可用性提示，注册最终写入仍由数据库唯一索引处理并发冲突。
- 新账号写入 `is_email_verified=false`，发送验证码成功后返回 202 并进入验证页；验证成功后标记已验证、自动登录并进入用户中心。网易配置示例使用 `sc_wiki@163.com` 发信。
- `POST /api/auth/verify-email` 验证 6 位码并签发会话；验证码有效 5 分钟、单次消费、最多错误 5 次。重发需要本次注册密码（仅保留在当前认证页面内存），未知邮箱和错误密码统一拒绝；重发受 60 秒冷却、邮箱/IP 每小时 5 次和 UTC 每天 10 次发送尝试限制。新码发送成功后替换旧码并清零尝试次数。
- Go API `POST /api/auth/login` 只接受邮箱和密码，要求 `account_status=active` 且邮箱已验证，返回 JWT、用户名、角色和一次更名资格，不返回实名。
- 用户写入失败时，只有 MySQL `1062` 唯一键冲突返回“邮箱或用户名已被占用”；其他数据库错误返回“注册失败”并记录服务端错误。
- 历史账号迁移后获得 `sc_` 加 12 位安全随机字符的临时用户名，可通过 `PATCH /api/auth/username` 成功自行更名一次；失败不消耗资格。
- 前端 `AuthContext` 将 token 和不含实名的用户信息保存到 `localStorage`，启动时通过 `GET /api/auth/me` 刷新服务端身份；通用 API 客户端自动附加 `Authorization: Bearer`。
- JWT 包含 `session_version`。Go 和 Python 权限解析都会校验数据库中的账号状态与会话版本；改密、封禁、注销或角色变化会递增版本，使旧 JWT 立即失效。

## 工作流程

用户提交注册资料后，服务创建未验证账号并发信；验证成功后前端保存 JWT 并返回来源页，无来源则进入用户中心。首次发信失败不会删除账号；用正确密码登录后可继续验证或重发，失败时不会声称已发信。后续上传、用户中心和工作台请求携带 token；中间件同时验证签名、会话版本、账号状态和角色。

## 忘记密码

登录页点击“忘记密码？”后进入邮箱 → 验证码 → 新密码/确认 → 返回登录流程。Go 提供 POST /api/auth/password-reset/request、verify、complete；与已登录账户中心要求旧密码的改密接口相互独立。

- 发送沿用现有 TLS 邮件组件和邮箱/IP 限流（60 秒冷却、每小时 5 次、UTC 每天 10 次）。仅向已验证且活跃账号发信，未知/未验证/非活跃邮箱使用统一受理响应。
- 6 位验证码 5 分钟有效，最多错误 5 次；验证成功原子消费并签发随机 32 字节的一次性改密令牌，5 分钟有效。Redis 仅保存 HMAC 摘要；令牌只在前端内存持有，不进入 URL 或浏览器存储。
- scope 绑定账号 ID、邮箱及 session_version，独立于注册和已登录改密码。重发成功撤销旧改密授权，发码/验证/修改使用用户行锁串行。
- 新密码至少 10 个字符、最多 72 UTF-8 字节，bcrypt 保存；成功递增 session_version，使所有旧 JWT 失效，不自动登录。
- 邮件、缓存或数据库故障明确报错；缓存不可用时不绕过验证码。数据库更新失败后已消费令牌不恢复，用户需重新取码。
- 统一受理正文不表示 SMTP 网络耗时无法区分账号状态。

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
- frontend/src/pages/AuthPage.tsx
- frontend/src/features/auth/
- frontend/src/lib/authNavigation.ts
- goserver/handlers/password_reset.go
- goserver/handlers/password_reset_test.go
- tests/02_identity_governance/auth-production-browser.mjs
- `frontend/src/components/UsernameField.tsx`
- `backend/username_policy.py`
- `backend/security.py`
- `alembic/versions/20260824_0009_add_account_identity_governance.py`
- `alembic/versions/20260821_0006_add_public_usernames.py`
- `tests/test_username_policy.py`
- `tests/07_researcher_community_forum/test_issue31_public_username.py`

## 相关变更记录

- [Feature #151：独立登录注册与邮箱找回密码](../../specs/151-superconducting-auth-page/spec.md)

- [Feature #31：唯一公开用户名与贡献榜身份](../../specs/31-community-ranking-visuals/spec.md)
- [GitHub Issue #31](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/31)

## 已知问题

- 当前提供邮箱验证码忘记密码，不提供邮箱变更流程。
- #151 已通过真实 Go 处理器与正式前端的隔离 HTTP 流程（SQLite、miniredis、邮件接口捕获），并通过邮件组件的本地 TLS/SMTP 测试。此验证不证明公网邮箱投递或生产 MySQL 并发锁行为已全部实测。
- 网易真实收信与目标环境完整注册流程仍待私密配置后的验收；自动化测试不证明外部投递。
