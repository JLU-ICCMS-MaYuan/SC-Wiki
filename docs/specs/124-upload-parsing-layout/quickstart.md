# 验收步骤：PDF 解析详情紧凑布局

## 前置条件

- 本地前端可访问，已登录且上传页存在一个未提交的 PDF 解析任务。
- 选用可滚动的解析草稿，分别设置桌面宽度约 1366px 与窄屏宽度 375px。浏览器不能缩至 375px 时，记录可达到的最窄宽度。

## 操作与预期

1. 打开 `/upload`，点击任务的“查看解析”。桌面左右边距各约 8px，解析栏较原来更矮。
2. 滚动到表单中段。栏贴合视口顶边，背景连续遮挡表单，文件名、阶段状态和“收起解析”仍可见；栏高度不超过 56px。
3. 在窄窗口重复滚动。按钮可点击，页面没有因工作区外边距新增的横向滚动；若不能达到 375px，记录实际测试宽度。
4. 点击“收起解析”。任务列表恢复，页面回到原有横向边距；待上传文件保留。

## 命令验证

```bash
cd frontend
NODE_OPTIONS='--localstorage-file=/tmp/scwiki-124-vitest-storage.json' npx vitest run --config ../vitest.config.ts ../tests/01_decentralized_uploading/upload-task-workspace.test.tsx
npm run build
```

预期：工作区回归测试和 TypeScript/Vite 构建均通过。当前 Node 26 运行 Vitest 时需提供临时 `localStorage` 文件。视觉与真实滚动效果按上述浏览器步骤核验。
