# 快速验收：邮箱验证注册

## 前置条件

- 空白测试邮箱、可用 Redis、测试 SMTP 或显式 fake sender。
- 应用通过 Docker Compose 启动。

## 路径

1. 注册合法用户名、邮箱和至少 10 位密码，确认页面进入验证码步骤且不存在管理员选项。
2. 检查邮件收到 6 位码，60 秒内重发被限制。
3. 提交错误码 5 次，确认旧码失效；重发后提交新码。
4. 确认验证成功自动进入 `/account`，刷新仍保持登录。
5. 使用已消费验证码重放，确认失败。
6. 检查数据库和生产日志不存在验证码明文。

## 验证命令

```bash
cd goserver && go test ./...
python3 -m pytest tests/02_maintenance_and_verification -q
cd frontend && npm run build
docker compose -f docker/compose.yaml config
```

## 2026-09-16 恢复验收补充

本地原生启动同样适用，不要求 Docker。使用根 README 的网易配置，授权码仅填入私密
`.env`；重新加载 Go 后，使用用户指定的未注册收件邮箱完成以下验收：

1. 注册进入验证码页，确认来自 `sc_wiki@163.com` 的邮件、中文主题和 6 位码。
2. 验证后自动进入用户中心，刷新及密码登录正常；原验证码不能重放。
3. 首次发信失败不显示“已发送”，可用原密码登录恢复验证，不覆盖用户名或密码。
4. 验证 60 秒冷却、5 次错误失效、新码重置次数、5 分钟过期和并发单次消费。
5. 已验证旧账号继续登录，封禁账号不能通过验证码恢复登录。

发送失败也计入尝试额度；小时与每日窗口按 UTC 计算。SMTP 接受邮件不代表收件箱收到，
真实验收必须包含收信确认。没有授权码或收件确认时，T018 保持未完成，Issue #39 不关闭。

自动化验证不向外部邮箱发信，使用隔离数据库、Redis 测试服务及真实本地 TLS SMTP 服务：

```bash
cd goserver
go test ./...
go test -race ./cache ./services
cd ..
./frontend/node_modules/.bin/vitest run --config vitest.config.ts tests/02_identity_governance/email-registration.test.tsx tests/02_identity_governance/identity_ui.test.tsx
cd frontend
npx tsc --noEmit -p tsconfig.app.json
npx vite build
```
