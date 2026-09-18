# 实施计划：邮箱验证注册

**GitHub Issue**：[#39](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/39)

**日期**：2026-08-24

**Spec**：[spec.md](spec.md)

## 摘要

在 Go 认证主链路新增 SMTP 发送抽象、Redis 原子挑战存储、验证与重发接口；注册固定创建普通用户，验证成功签发包含会话版本的 JWT。前端沿用现有验证码步骤并补重发与自动登录。

## 技术上下文

- **语言与版本**：Go 1.25、TypeScript 5、React 19、Python 3.10（迁移测试）。
- **主要依赖**：Gin、GORM、go-redis、bcrypt、MUI、Vitest。
- **数据存储**：MySQL 用户验证事实；Redis 验证码摘要、TTL 与额度。
- **测试体系**：Go `testing/httptest/sqlmock/miniredis`、Vitest、Pytest Alembic 契约测试。
- **目标平台**：Docker Compose，Go 服务为 `/api/auth/**` 入口。
- **性能目标**：发送和验证均为常数次 Redis/MySQL 操作；接口超时不得超过外部 SMTP 超时上限。
- **约束**：验证码不得明文持久化或记录；Redis/SMTP 失败关闭。
- **规模范围**：单站点注册流量，按邮箱和 IP 双维度限流。

## 质量门

| 约束来源 | 强制要求 | 设计如何满足 | 状态 |
|---|---|---|---|
| AGENTS.md | Alembic 管理迁移，文档简体中文 | 单一迁移 head，三模型同步 | 通过 |
| #31 | 用户名唯一、邮箱登录 | 注册复用现有用户名校验 | 通过 |
| FR-003/005 | 单次消费与原子限流 | Redis Lua/事务封装 | 通过 |
| Overview | 当前 Go 缺少验证端点 | 新接口只在 Go 注册 | 通过 |

## Feature 文档结构

```text
docs/specs/39-email-verified-registration/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/auth-api.md
├── tasks.md
└── checklists/requirements.md
```

## 源代码结构

```text
goserver/handlers/auth.go
goserver/services/email.go
goserver/services/verification.go
goserver/middleware/auth.go
goserver/cache/cache.go
goserver/config/config.go
frontend/src/context/AuthContext.tsx
frontend/src/components/AuthDialog.tsx
alembic/versions/<next>_account_identity_foundation.py
docker/compose*.yaml
docker/.env.example
```

**结构选择**：认证 Handler 只编排请求，验证码原子状态和 SMTP 分别封装，避免把外部 IO、限流和用户事务堆在现有 `admin.go`。

## 需求到设计的映射

| 来源 | 设计组件/接口 | 验证方式 |
|---|---|---|
| FR-001/007 | 注册与登录 Handler | 角色注入和未验证登录测试 |
| FR-002/003/006 | 邮件服务、验证挑战、验证接口 | 发送失败、单次消费、自动登录测试 |
| FR-004/005/009/010 | Redis 原子额度服务 | miniredis/Lua 与错误语义测试 |
| FR-008 | AuthDialog | Vitest 注册流程测试 |

## 阶段与依赖

1. 建立账号身份基础迁移、JWT 会话版本和邮件配置。
2. 实现验证码状态、SMTP 和 Go API。
3. 改造前端注册验证状态机。
4. 运行迁移、行为、构建和 Compose 验证。

## 2026-09-16 收敛设计

复用 Go 认证、Redis 和现有前端验证界面，不增加数据表、依赖或第二套 Python 认证。恢复注册返回 202、未验证登录返回 403；旧已验证账号继续登录。

- Redis Lua 一次检查邮箱冷却及邮箱/IP 小时、UTC 自然日配额，通过后原子预留；超额不消耗其他额度。全部重发请求先进行相同配置及额度检查，再校验邮箱与密码；未知邮箱执行等成本 bcrypt 比较，统一返回 401，正确凭据才决定是否发信。
- SMTP 在 20 秒总期限内完成 TLS、认证及发送；465 使用 implicit TLS，STARTTLS 必须成功升级，不允许明文降级。中文主题使用标准 MIME 编码，验证收发地址，拒绝头部注入。
- SMTP 接受邮件后才原子替换验证码摘要并重置错误次数；失败保留旧挑战，发送冷却保持 60 秒，避免并发发送与失败滥用。SMTP 成功后 Redis 写入失败仍返回 503，用户可重发恢复。
- 验证失败 5 次锁定当前码，重发新码重置；原子消费只允许一次验证。账号封禁/注销不得通过验证签发会话；数据库写入失败时返回失败且可重发。
- 前端保留结构化错误码及 Retry-After，注册邮件失败或未验证登录均提供继续验证入口，不能把失败显示成“邮件已发送”。
- 配置示例使用 SMTP_HOST=smtp.163.com、SMTP_PORT=465、SMTP_USER/SMTP_FROM=sc_wiki@163.com、SMTP_TLS_MODE=implicit；密码不入库。

### 收敛追踪

| 需求 | 组件 | 任务 | 证据 |
|---|---|---|---|
| FR-001/002/006/007 | Go 注册、登录、验证 | T013 | HTTP + 数据库 + Redis 流程测试 |
| FR-003/004/005/009/010 | Redis、SMTP | T014/T015 | 原子并发与本地 TLS SMTP 协议测试 |
| FR-008、SC-001 | AuthContext、AuthDialog | T016 | 前端请求、验证码和恢复交互测试 |
| SC-002/003/004 | 上述组件 | T017 | 回归测试、日志检查及真实收信验收 |

- 前端重发携带弹窗内已有密码，登录恢复验证时同步当前密码；不持久化密码。请求期间禁止关闭/切换，防止迟到响应丢失邮箱。
- Go 仅信任 TRUSTED_PROXIES 配置的代理（本地默认回环），只读取被 Nginx/Vite 覆盖的 X-Real-IP；Docker 默认代理网络 172.16.0.0/12，不向公网暴露 Go 端口。
