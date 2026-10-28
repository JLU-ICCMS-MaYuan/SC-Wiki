# 多标签页认证同步验收

日期：2026-10-28。关联：[Issue #171](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/171)、[规格](spec.md)、[机器结果](validation.json)。

## 结果

- 认证、导航、账户和侧栏五个测试文件共 60 项通过。
- 编辑器已有未保存保护两项通过；合计 62 项相关测试，不代表全仓库测试已全部运行。
- Chrome 156.0.8078.48，同一 BrowserContext 五个真实页面，连续十轮退出重登和账号交替通过。
- 真实 Go 认证处理器、内存 SQLite、miniredis 与捕获邮件夹具；所有 /api/auth 请求均经过真实 HTTP 处理器。其他业务响应隔离，旧 401 场景额外注入故障。
- TypeScript 检查与 Vite 正式构建通过；构建保留既有 3Dmol eval 与大包提示。

## 对照与故障边界

新增的 17 项认证同步测试在原代码下 15 项失败、2 项通过；修复后全部通过。覆盖跨页登录/退出、focus/visibilitychange 补漏、旧成功/401/503/网络失败响应、相同 JWT 的不同世代、明确失效、事件去重、未完成登录被退出取消、旧资料/更名响应与卸载隔离。

编辑器保护原测试曾在“保存后解除 beforeunload”失败。通过临时 Vitest 配置只加载 Git 中修改前的 AuthContext/AuthPage，保持其余工作树相同，失败仍复现。原因是测试的 api 替身只有 get/put/post，遗漏现有 createFieldDraftSaver 使用的 patch。仅在该测试补齐 patch 及成功返回值后，两项通过；未修改编辑器业务代码，也未纳入同文件中其他任务已有的候选展示测试改动。

本机 Node 26 的实验 Web Storage 会干扰 jsdom；运行 Vitest 时采用进程级 `NODE_OPTIONS=--no-experimental-webstorage`，没有改系统配置或依赖。

## 需求到证据

| 标准 | 验证与结果 |
| --- | --- |
| SC-001 / FR-001、FR-002、FR-005 | 五页十轮全部成功；每页使用真实通用 api 客户端调用 /me，返回同一当前用户名。共 14 次主动登录（首次、十轮、冻结恢复、两次竞态），其他标签页没有额外提交登录。 |
| SC-002 / FR-003 | 十轮源页完成登录后等待其他页完成的时间为 11～37 ms；退出含点击操作为 323～406 ms。真实 CDP 冻结后台页，其他页退出并登录另一账号后恢复，12 ms 内同步。独立记录 /me 往返为 1～6 ms。所有有界等待均小于两秒。 |
| SC-003 / FR-004 | 浏览器延迟真实旧 /me 成功响应以及注入旧 401，重新登录后释放，五页仍为新会话；组件测试另覆盖同 JWT 不同世代、5xx、网络失败、迟到资料修改。 |
| SC-004 / FR-006、FR-007 | 两个预先打开的登录页分别安全返回带 query/hash 的站内来源和热点（拒绝外站）；普通搜索页 URL、输入及文档实例标记十轮保持。本页注册默认进入账户中心、侧栏输入/文件保留及编辑器离页保护均有通过的回归测试。 |

## 实际命令

仓库根目录：

```sh
NODE_OPTIONS=--no-experimental-webstorage frontend/node_modules/.bin/vitest run --config vitest.config.ts tests/02_identity_governance/auth-sync.test.tsx tests/02_identity_governance/auth-page.test.tsx tests/02_identity_governance/email-registration.test.tsx tests/02_identity_governance/sidebar-navigation.test.tsx tests/02_identity_governance/account-center.test.tsx
NODE_OPTIONS=--no-experimental-webstorage frontend/node_modules/.bin/vitest run --config vitest.config.ts tests/01_decentralized_uploading/upload-task-editor-layout.test.tsx -t "独立解析标签页未保存保护"
```

在 frontend 运行 `npm run build`。浏览器按 [quickstart.md](quickstart.md) 运行，使用独立 127.0.0.1:5179 前端测试进程与 TestAuthBrowserFixture，已正常结束 Go 夹具。

## 限制与关闭门

- 不声称用户当前浏览器的历史故障已原样复现，也不声称在线站点已发布修复；证据支持当前源码的同步、竞态与导航行为。
- 测试不涉及生产账号、持久化数据库或真实邮件投递；不验证不同浏览器、配置或无痕隔离间同步。
- 无业务界面重设计，无新依赖、后端协议或数据库迁移；采用统一同步入口和原生事件，避免轮询和重复状态库。
- Spec 仅本地保存，Issue 已登记路径。未授权 Git 推送，双向远程链接尚未核验；Issue 保持开放。
