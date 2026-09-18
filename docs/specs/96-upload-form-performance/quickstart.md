# 快速验收：上传解析记录表单性能修复

## 前置条件

- Node.js 与仓库内 `frontend/node_modules` 已安装。
- 工作目录为仓库根目录 `/home/mayuan/code/SC-Wiki`。

## 定向测试

```bash
./frontend/node_modules/.bin/vitest run --config ./vitest.config.ts \
  tests/01_decentralized_uploading/material-states-editor.test.tsx \
  tests/01_decentralized_uploading/property-record-editor.test.tsx \
  tests/01_decentralized_uploading/upload-task-editor-layout.test.tsx \
  tests/01_decentralized_uploading/upload-form-performance.test.tsx
```

预期：所有用例通过；其中性能回归用例验证未修改状态/记录的渲染计数、空间群输入提交和定义请求去重。

## 类型与生产构建

```bash
./frontend/node_modules/.bin/tsc -p frontend/tsconfig.json --noEmit
npm --prefix frontend run build
```

预期：TypeScript 检查和 Vite 生产构建均成功。

## 手工检查

1. 启动前端开发服务并打开 `/upload`，选择一个已经进入 `ready` 的上传任务。
2. 在包含多个材料状态的解析记录中修改第一个状态的晶系、空间群和结构家族。
3. 连续输入空间群符号后选择候选，再切换到另一个材料状态确认值未串改。
4. 打开模块化物性记录，修改一个枚举字段，确认其他记录内容、折叠状态和错误提示不变。
5. 等待 5 秒，确认只发生一次现有草稿自动保存；提交载荷字段与优化前一致。
