# 验收步骤

## 自动化

1. 在仓库根目录运行 `frontend/node_modules/.bin/vitest run --config vitest.config.ts tests/02_identity_governance/auth-sync.test.tsx tests/02_identity_governance/auth-page.test.tsx tests/02_identity_governance/email-registration.test.tsx`。Node 26 如遇 jsdom 的 localStorage 冲突，按 [验收记录](validation.md) 使用进程级 NODE_OPTIONS。
2. 使用独立端口启动前端测试服务；运行已有 Go TestAuthBrowserFixture，fixture 数据仅位于内存 SQLite/miniredis。
3. 运行 `node tests/02_identity_governance/auth-cross-tab-browser.mjs`；通过 FRONTEND_URL、AUTH_FIXTURE_FILE、PLAYWRIGHT_MODULE、CHROMIUM_PATH、ARTIFACT_DIR 指定隔离环境。
4. 在 frontend 执行 `npm run build`，检查 TypeScript 与正式打包。
5. 结果、范围与限制记录在 validation.md，不上传凭据。

## 浏览器场景

同一 BrowserContext 新建五页，三页业务页、两页登录页；从一页登录后校验账号及 /me 身份。十轮主动退出再登录，每页均无需重复登录或刷新。
记录同步耗时、保持业务页 URL 与输入；延迟旧 /me 后重新登录，再放行成功/失败响应，确认新状态未改变。
后台恢复需覆盖真实后台页面切换；通过事件遗漏模拟补测恢复兜底，不把合成事件当成真实浏览器冻结证据。

## 手工验收

用户浏览器同源五个页面重复上述操作。普通与无痕窗口、不同浏览器不属于范围。未发布到目标环境前，不能宣称用户当前在线站点已修复。
