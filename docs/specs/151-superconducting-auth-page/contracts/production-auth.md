# 正式认证契约

## 前端与路由

/auth 是 AppShell 外的独立页面，lazy 加载共享认证展示组件；Demo 通过显式模拟适配器继续可打开，生产构建不能导入 mockAuth。界面、动画和找回表单共享；生产服务由 AuthContext 和独立找回 API 封装提供。

入口携带 returnTo 查询参数，只接受单斜杠开头的站内路径，不含反斜线、控制字符或编码后的这些字符，禁止 /auth、/auth-demo.html 循环；来源路径含原 query/hash。登录或注册验证成功优先返回来源；无来源分别 /news 与 /account。返回按钮回来源或 /news。

现有 login/register/verify-email/resend-verification 与 username-availability 接口不改契约。注册已建账号但发信失败须进入可重发的验证页，不把失败写成已发信。密码只保留于页面内存。

## 新增公开 API（Go）

- POST /api/auth/password-reset/request：{email}；202 {resend_after_seconds:60, expires_in_seconds:300, message}，对未知/非活跃/未验证账号同样受理但不发信；同样检查邮箱/IP限流。已验证活跃账号通过现有 TLS 邮件发送密码操作验证码，成功后发布独立重置码。
- POST /api/auth/password-reset/verify：{email,code}；200 {reset_token,expires_in_seconds:300}。6 位数字，错误计数最多 5 次，Redis 原子消费；生成 32 字节随机一次性令牌，只保存 HMAC 摘要。
- POST /api/auth/password-reset/complete：{email,reset_token,new_password}；204。新密码至少 10 Unicode 字符、最多 72 UTF-8 字节；事务行锁重新检查邮箱/账号活跃且已验证/session_version，原子消费令牌，bcrypt 写入并递增 session_version。成功后不签发登录 token，必须重新登录。

重置码 scope 包含 user.id、session_version、规范化邮箱哈希，与注册及 password-change 独立；重发成功替换原重置码且撤销已发放的改密授权。请求、验证码验证、最终改密通过相同用户行锁串行，使并发重发/验证/修改不会颠倒。数据库失败后的已消费码/令牌不可重试，前端提供重新获取路径。

通用错误：400 invalid_email / invalid_verification_code / invalid_reset_token / invalid_password；429 verification_rate_limited（Retry-After）或 verification_attempts_exceeded；503 verification_send_failed / verification_unavailable。无原始验证码、密码或令牌日志。

Redis 断连时失败关闭，不旁路；注册验证码与已登录改密码不能转换为找回授权。未知邮箱统一响应只保证状态/正文一致，不宣称网络/SMTP耗时不可区分。
