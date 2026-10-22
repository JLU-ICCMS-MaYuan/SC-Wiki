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
