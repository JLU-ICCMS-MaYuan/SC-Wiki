# 本地评审指南

当前交互预览已启动于 `http://127.0.0.1:5174/nobel-demo.html`；最终漫画重绘尚未完成。从仓库重新运行：

```bash
cd frontend
npm run dev -- --open /nobel-demo.html
```

Vite 默认地址为 `http://localhost:5173/nobel-demo.html`。如果 `5173` 已被占用，使用终端显示的端口。人物详情会由肖像链接在新标签页打开；也可在地址后加 `?person=onnes` 等人物 ID 检查详情模式。

建议依次检查：

1. 12 位人物是否都出现，头像是否能辨认。
2. 环形展陈是否缓慢转动，悬停/键盘聚焦是否暂停，移开后是否恢复。
3. 肖像下的姓名、年份、获奖时身份和获奖成果是否对应。
4. 详情页的经历和获奖贡献是否有对应可打开引用。
5. 键盘操作、窄屏布局以及系统“减少动态效果”设置。
6. 对照 `assets/portrait-manifest.json` 的 SHA-256 确认 Demo 图片即所列复用资产。

生产前端仍通过常规入口访问；本 Demo 不替换 `/news` 中现有内容。

浏览器回归：在仓库根目录运行 `node "tests/07_researcher_community_forum/nobel-demo-browser.mjs"`。需要本机 Chrome；脚本默认复用 `prototypes/account-center/node_modules/playwright`，也可通过 `PLAYWRIGHT_MODULE` 指定已有 Playwright 模块，`NOBEL_DEMO_URL` 指定预览地址。
