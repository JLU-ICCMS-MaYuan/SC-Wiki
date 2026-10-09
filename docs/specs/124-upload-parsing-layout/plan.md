# 实施计划：PDF 解析详情紧凑布局

**GitHub Issue**：[#124](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/124)

**日期**：2026-10-09

**Spec**：[spec.md](spec.md)

## 摘要

原实施由 `UploadPage` 在解析详情展开时抵消 `AppShell` 的部分内边距，保留左右各 8px；常驻栏从视口顶边粘附并压缩竖向内边距。后续 #126 改为由 `AppShell` 统一提供全站 8px 边距，上传页移除状态性抵消，收起后也保持 8px。沿用原有按钮、轮询和表单组件。

## 技术上下文

- **语言与版本**：React 19、TypeScript 5.6。
- **主要依赖**：MUI 7、Vite 5。
- **数据存储**：不涉及。
- **测试体系**：Vitest、Testing Library，上传工作区测试位于 `tests/01_decentralized_uploading/upload-task-workspace.test.tsx`。
- **目标平台**：桌面与移动浏览器的 `/upload` 页面。
- **性能目标**：不增加网络请求或渲染组件。
- **约束**：保持现有语义角色和按钮行为；全站主内容边距的后续调整由 #126 实施。
- **规模范围**：单页布局与现有回归测试。

## 质量门

| 约束来源 | 强制要求 | 设计如何满足 | 状态 |
|----------|----------|--------------|------|
| AGENTS.md | 在 `mayuan` 分支修改，保留无关工作树改动 | 修改前核对分支，提交仅暂存本次路径 | 通过 |
| Overview | 上传页继续使用现有校对和任务入口 | 只修改页面根容器及现有常驻栏样式 | 通过 |
| FR-001、FR-002 | 紧凑、完整遮挡、可操作 | 保持按钮 44px，常驻栏顶部偏移归零，使用不透明背景 | 通过 |
| FR-003、FR-004 | 展开与收起均为 8px，窄屏无溢出 | #126 将边距收敛至公共壳层 | 由 #126 实施 |

## Feature 文档结构

```text
docs/specs/124-upload-parsing-layout/
├── spec.md
├── plan.md
├── research.md
├── quickstart.md
├── tasks.md
├── contracts/sticky-layout.md
└── checklists/requirements.md
```

## 源代码结构

```text
frontend/src/pages/UploadPage.tsx
tests/01_decentralized_uploading/upload-task-workspace.test.tsx
docs/overview/01_Decentralized_Uploading_of_Superconductivity_Data/README.md
```

**结构选择**：原局部边距属于上传页状态；#126 将其提升为全站当前约束，`AppShell` 成为唯一外层边距来源，`UploadPage` 不再保留负边距特例。

## 需求到设计的映射

| 来源 | 设计组件/接口 | 验证方式 |
|------|---------------|----------|
| FR-001、FR-002 / US1 | `UploadPage` 常驻栏 | `quickstart.md` 桌面滚动与高度检查 |
| FR-003、FR-004 / US1 | `UploadPage` 根容器 | `quickstart.md` 桌面和窄屏间隙检查 |
| FR-005 / US1 | 既有收起逻辑 | 上传工作区回归测试 |

## 阶段与依赖

1. 确认原有布局和测试基线。
2. 实施局部布局调整，更新既有回归断言。
3. 运行验证、回写当前功能 Overview，核对 Issue 验收。
