# 验收步骤：全站页面主体窄边距布局

## 视口与路由

- 依次使用 375px、768px、1366px 和宽桌面视口；侧栏在可用时分别展开与收起。
- 覆盖热点、探索各阶段、脉络、社区图表/排行/讨论及详情、上传、对话、Tc 估算、论文详情与返修、账户与公开主页、通知、管理员与超级管理员工作台、管理员论文编辑和错误/未登录状态。

## 观察信号

1. 页面主体与侧栏右缘、视口右缘各相隔约 8px；普通页面上下间距仍分别为窄屏 16px、桌面 32px。
2. 账户、社区、管理等原居中页面的主要卡片填充可用空间；文字段落与弹层不被强行拉宽。
3. 上传解析展开、滚动和收起均保持 8px 边距；常驻栏贴顶且不透出表单，收起按钮可点击，待上传文件保留。
4. 文档根节点的 `scrollWidth` 不大于视口宽度；宽表格、图表只在自身容器内滚动。窄屏下 Tc 估算和管理员编辑字段重排，RAG 聊天区域不溢出。

## 命令验证

```bash
cd frontend
NODE_OPTIONS='--localstorage-file=/tmp/scwiki-126-vitest-storage.json' npx vitest run --config ../vitest.config.ts --no-file-parallelism ../tests/01_decentralized_uploading/upload-task-workspace.test.tsx ../tests/02_identity_governance/sidebar-navigation.test.tsx ../tests/02_identity_governance/admin-edit-page.test.tsx
npm run build
```

按实际修改的功能补充定向回归；构建和测试通过后再回写 Overview。视口几何与真实溢出需要浏览器验收，不能仅靠 jsdom 样式断言替代。

## 本地执行记录（2026-10-09）

- 上述三个文件按顺序运行：34 项测试通过；TypeScript/Vite 生产构建通过。
- 浏览器实测公共壳层在 375、768、1366、2048px 下左右均为 8px，上下分别为 16/32px；侧栏收起后仍为 8px。
- 375px 下热点、探索、脉络、社区、上传与 Tc 估算均未出现页面级横向滚动；对话页实际根容器在 375、768、1366、2048px 均贴合 8px 边距，`scrollWidth` 等于视口宽度。
- 社区讨论与 Tc 估算在 768、2048px 的主体均贴合 8px 边距且没有页面级横向滚动。管理员编辑通过组件回归和响应式网格代码核验；本机浏览器没有管理员登录态，未取得该路由的实页截图。
