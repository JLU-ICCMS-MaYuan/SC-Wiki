# Demo 预览与验收

## 打开

- 登录页面：<http://127.0.0.1:5173/auth-demo.html>
- 入口跳转演示：<http://127.0.0.1:5173/auth-demo.html?view=entry>
- 如果当前没有运行前端，在仓库 frontend/ 运行 `npm run dev -- --host 127.0.0.1`。以 Vite 实际输出端口为准。

这是独立 HTML 开发入口。正常生产构建仍只包含 index.html，不发布 Demo；正式侧栏和上传页仍调用原来的登录弹窗。

## 演示账号与操作

1. 点击“查看演示账号”可填入账号。已验证账号为 researcher@example.com，未验证账号为 unverified@example.com，密码都是 demo123456。
2. 正确登录显示演示成功；错误密码显示错误，原有正式认证存储不变。
3. 切换注册，填写新的用户名和邮箱、至少 10 位密码；用户名沿用正式本地校验。可选实名填写前会说明其公开可见性。
4. 注册后输入 000000 查看错误，再输入 123456 验证成功。60 秒内禁止重发，5 分钟后过期，5 次错误后需重新发送；这些都是内存演示规则。
5. 未验证账号登录后点击“重新发送验证码”，可继续验证；不会收到真实邮件。
6. 顶部切换中英文；键盘左右键切换登录/注册标签，Tab 进入字段。密码显隐、错误提示和验证码步骤可操作。
7. 动画约 16 秒绕行一周，可暂停/播放；系统减少动态效果默认静止。短屏允许纵向滚动。
8. 成功后返回演示入口，可体验“侧栏登录入口”和“上传页登录入口”的跳转；此处仅模拟返回来源页。

不要使用真实密码；Demo 刷新后内存数据重置。没有真实邮件、账号创建、token 签发或生产用户登录。

## 自动化验证

在 frontend/ 执行：

```bash
NODE_OPTIONS="--no-experimental-webstorage" npm exec vitest -- run --config "../vitest.config.ts" "tests/02_identity_governance/auth-demo.test.tsx"
npx tsc -b
npm run build
```

Node 26 的内置 Web Storage 与当前 Vitest/jsdom 环境冲突，因此第一条命令只在该进程禁用 Node 自带 Web Storage，不修改系统或项目配置；浏览器仍使用真实 localStorage。

在仓库根执行浏览器脚本：

```bash
node "tests/02_identity_governance/auth-demo-browser.mjs"
```

脚本可通过 PLAYWRIGHT_MODULE、CHROMIUM_PATH、FRONTEND_URL、ARTIFACT_DIR 指定本机 Playwright、Chromium、开发服务和输出目录。使用单独浏览器上下文，拦截所有 /api 请求，不接触浏览器现有登录资料。当前运行用本机 Chrome 无头进程；已获得用户明确授权。

## 本次结果（2026-10-22）

- Vitest：6/6 通过；覆盖注册、登录、验证、过期、错误次数、重发、重置隔离、未验证恢复、语言切换及认证存储隔离。
- TypeScript、正式前端构建和指定 auth-demo.html 的独立 Vite 构建均通过。后者输出到 /tmp/scwiki-auth-demo-final-build，不进入生产目录。
- 浏览器：17 个视口/语言/状态组合无横向溢出；键盘与主要认证演示流程通过；零 API 请求、零页面异常。
- 动画：观测 16 秒完整周期、暂停恢复、减少动画；后台暂停以 visibilitychange 事件注入验证，未声称完成真实操作系统后台标签验收。
- 原始机器结果：[browser-results.json](assets/browser-results.json)。视觉证据和迭代见 [design-qa.md](design-qa.md)。
- 现有构建仍提示 3Dmol 的 eval 和较大分包告警，构建退出码为 0；这些不属于本 Demo 变更。

## 当前停止点

第一阶段交互 Demo 已提供预览；用户视觉评审尚未完成。第二阶段 /auth、正式入口替换、真实认证回归、Overview 更新、远程 Spec 链接核验均未实施或未完成，Issue #151 保持开放。
