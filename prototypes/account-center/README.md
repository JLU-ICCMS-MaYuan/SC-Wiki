# SC-Wiki 用户中心交互 demo

对应 [Issue #152](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/152) 与 [Spec](../../docs/specs/152-account-center-demo/spec.md)。

独立 React 原型，顶部切换普通用户、管理员、超级管理员。使用示例资料和贡献关系，不连接生产接口。工作入口打开独立演示标签页；真实工作模块的完整实现不在此原型中。

启动：`npm ci` 后执行 `npm run dev -- --host 127.0.0.1 --port 5186 --strictPort`。构建：`npm run build`。浏览器检查：`node scripts/verify-browser.mjs`，需启动本地服务并安装 Chrome。

原站导航指向本机 5173，需要已有 SC-Wiki 开发服务。文献 DOI 链接指向原文。没有真实账户写入、真实审核、部署或推送。
