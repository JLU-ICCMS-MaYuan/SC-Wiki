# Demo 认证边界

本契约是浏览器内存函数，不是 HTTP API；所有方法延迟约 450ms 后返回或抛出可翻译的机器错误键。

| 方法 | 输入 | 结果与错误 |
| --- | --- | --- |
| login | email、password | 成功；credentials 或 unverified |
| register | email、password、username、realName | 创建内存账号并准备模拟验证码；invalidUsername、shortPassword、taken |
| verify | email、code | 验证成功；invalidCode、expired、tooManyAttempts |
| resend | email | 返回 60 秒冷却；cooldown 或 credentials |

固定演示账号：researcher@example.com；未验证账号：unverified@example.com；密码均为 demo123456。验证码 123456。正式账号不适用于 Demo。

演示页面不挂载生产 AuthProvider；不得发出 /api/auth 请求，不写 sc-wiki 的认证存储。仅语言偏好沿用现有 LanguageProvider。

第二阶段沿用 POST /api/auth/login、register、verify-email、resend-verification 以及用户名可用性接口，当前不新增或修改它们。

## 密码重置演示扩展

- requestPasswordReset(email)：统一显示准备验证码结果；已验证模拟账号才建立挑战；60 秒重发冷却。
- verifyPasswordReset(email, code)：验证 123456，5 分钟有效、最多错误 5 次；返回一次性改密凭证并消费验证码。注册验证码不能替代该挑战。
- resetPassword(email, grant, newPassword)：仅匹配邮箱、凭证未过期/未消费且密码至少 10 位时改动模拟账号；不自动登录。
- cancelPasswordReset(email)：离开找回界面时清除当前邮箱的临时改密授权，验证码冷却保持。

以上不新增生产 HTTP API；不能用于真实账号或安全性证明。
