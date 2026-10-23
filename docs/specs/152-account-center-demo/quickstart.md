# 查看 demo

## 邮箱验证码改密体验

展开账户安全，输入演示旧密码 `DemoOld123!` 和账户邮箱 `mayuan@example.com`，点击“验证并发送验证码”；使用模拟码 `246810`，输入至少 10 位新密码并确认，再点击“验证并修改密码”。不发送真实邮件，请勿输入真实密码；刷新恢复初始演示凭证。

专项验证：`node scripts/verify-password.mjs`。

## 启动与其他操作

在仓库根执行：

```bash
cd "prototypes/account-center"
npm ci --prefer-offline --no-audit --no-fund
npm run dev -- --host 127.0.0.1 --port 5186 --strictPort
```

浏览器打开 `http://127.0.0.1:5186/?role=superadmin`，顶部可切换三种角色。

1. 默认资料不可编辑；点击修改，分别尝试取消和保存。
2. 检查普通用户无检查列表，管理员在收录列表下看到检查记录和待检查队列。
3. 输入不存在的论文关键词，检查空态及重置。
4. 点击六个超级管理员入口，检查新标签页标题和实际显示的模块。
5. 调整为手机宽度，检查换行和横向溢出。

验证：`npm run build`；`node scripts/verify-browser.mjs`（需已安装 Chrome 或通过 PLAYWRIGHT_CHROMIUM_EXECUTABLE 指定 Chromium，且本地服务已运行）。

所有资料保存、申请、模型设置均只作用于示例内存，刷新恢复。导航到原站的链接依赖原站 5173 服务，不属于本轮 demo 验收。
