# 演示验收记录

## 正式接入验收（2026-10-23）

- 正式实现：AccountPage/AccountSecurity/AccountReviews/AccountWorkEntries，真实本人检查接口、SMTP 改密码及服务端强制验证；原型与正式入口分别保留在 5186 和本机 5173。
- 前端：账户、身份导航、论文详情相关 28 项通过，正式 `npm run build` 通过；英文 AccountPage/AdminPage 两项使用 Node 22 通过。当前 Node 26 的既有巡检存在 localStorage 环境错误，未修改其测试逻辑来规避。
- 后端：完整 `go test ./...` 首次发现本项测试夹具缺 user_email，修正后专项通过；另一个既有 `TestApplyPaperEvidenceArchivesManualReasonInReviewTransaction` 的 SQL 期望失败，在未修改 HEAD 的独立快照中复现。本项不改证据审核语义；明确排除该既有用例后的全包检查通过。
- 安全回归：发送前旧密码／绑定邮箱校验、缺码拒绝、用途／账户隔离、错误次数、过期、重发、SMTP/Redis 故障拒绝、成功撤销会话、并发仅成功一次及请求处理中已撤销会话拒绝，均通过。
- 邮件：本地真实 TLS SMTP fixture 已收到改密邮件，验证标题与改密用途内容；这不代表外部邮箱已收到真实邮件。本轮未给用户真实地址发信。
- 浏览器：正式 React 页面三角色、编辑取消／保存、待检查复用、六个新标签页模块、1440px 桌面及 390/320px 小屏通过，零页面脚本错误；使用隔离 API 响应，不修改真实账户或论文。后端数据与安全通过真实处理器测试分别验证。
- 视觉：原型与正式截图合并查看；原站导航保留，列表按实际响应条数展示。窄屏论文状态改为独立一行，320px 工作入口单列。证据在本地 `prototypes/account-center/qa/production/`，详见 [正式视觉记录](production-design-qa.md)。
- 本地新发码路由无认证请求返回 401；开发服务自动重载。没有推送、生产部署或数据库迁移。

### 可重复验证

```bash
cd "goserver"
../.local/go/bin/go test ./... -skip '^TestApplyPaperEvidenceArchivesManualReasonInReviewTransaction$'
cd "../frontend"
npm run test:upload-ui -- ../tests/02_identity_governance/account-center.test.tsx ../tests/02_identity_governance/identity_ui.test.tsx ../tests/01_decentralized_uploading/paper-detail-route.test.tsx
npm run build
cd ".."
node tests/02_identity_governance/account-center-browser.mjs
```

Go 完整检查的既有失败没有被删除、修复或计作通过；Issue 因远程文档尚未推送而保持开放。

## 2026-10-23：邮箱验证码改密演示

- `node scripts/verify-password.mjs`：三角色完整流程通过。未填旧密码或邮箱不能发送，错误旧密码或非绑定邮箱不能进入第二步；错误或过期验证码、相同新旧密码、确认不一致均拒绝修改。
- 60 秒重发、5 分钟过期使用浏览器时钟推进验证；重发清空验证码，成功后旧演示密码失效。取消、重新验证与角色切换清除输入和挑战。
- 桌面及 390/320px 两步骤截图检查；手机身份提示分行，邮箱完整可读，无横向溢出。页面错误及写请求均为零；独立构建通过。
- 演示凭证、时效仅为可逆默认；真实邮件、安全校验和会话失效未实施。

## 首轮演示

2026-10-22，独立 demo；正式视觉评审和生产接入仍待用户反馈。

- `npm run build`：通过，生成独立原型制品。
- `node scripts/verify-browser.mjs`：三角色资料只读／取消／保存／非法 ORCID，搜索筛选、空态、详情、待检查队列、七个新标签页直达均通过。
- 1440／2048 桌面、768／390／320 小屏检查；小屏只读与编辑无横向溢出。
- 公开页邮箱隐藏、普通用户管理深链受限；仅前端示例行为，不当作生产鉴权验收。
- 页面错误 0，非 GET／HEAD 请求 0；无真实账户或科学审核写入。
- 视觉比对与字号修复记录见 [设计检查](../../../prototypes/account-center/design-qa.md)。
- 只修改本项原型及文档，保留原工作树并行修改；不推送、不部署、不关闭本 Issue。
