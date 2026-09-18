# 实施计划：上传解析记录表单性能修复

**GitHub Issue**：[Issue #96](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/96)

**日期**：2026-09-09

**Spec**：[spec.md](spec.md)

## 摘要

在现有受控草稿模型上增加材料状态和物性记录的渲染隔离。材料状态卡片使用稳定的状态引用和记忆化边界；空间群自由输入保留本地值；选项、动态 Schema 与校验结果使用记忆化计算。物性定义绑定 effect 只在定义身份真正变化时更新本地状态。保存和提交仍由 `UploadTaskEditor` 负责，接口不变。

## 技术上下文

- **语言与版本**：TypeScript 5.6、React 19。
- **主要依赖**：MUI 7、Vitest 2、Testing Library。
- **数据存储**：不变，草稿仍保存在 Redis，提交仍走现有 API。
- **测试体系**：`vitest.config.ts` 中的上传目录 `.test.tsx`，前端 `npm run build`。
- **目标平台**：Vite 开发构建和生产构建的浏览器表单。
- **性能目标**：未修改的材料状态/物性记录不因无关编辑产生渲染提交；自由输入不逐字符更新父级草稿；定义请求不重复增加。
- **约束**：不新增依赖、不改变受控数据结构和现有自动保存节流。
- **规模范围**：多材料状态、每状态多个模块和动态记录，空间群目录最多 230 项。

## 质量门

| 约束来源 | 强制要求 | 设计如何满足 | 状态 |
|----------|----------|--------------|------|
| AGENTS.md | 文档使用简体中文、修改后按明确路径提交 | 本目录文档全中文；提交只暂存本 Feature 文件 | 通过 |
| Issue #96 | 选项编辑响应提升且数据契约不变 | 渲染边界、局部输入和缓存只改变前端计算范围 | 通过 |
| Overview | 上传草稿、自动保存和提交行为保持现状 | 不改 API、草稿字段或保存触发时机 | 通过 |
| KISS / YAGNI | 不引入新状态库或虚拟化框架 | 复用 React.memo、useMemo、useCallback 和现有组件 | 通过 |

## Feature 文档结构

```text
docs/specs/96-upload-form-performance/
├── spec.md
├── plan.md
├── research.md
├── quickstart.md
├── tasks.md
└── checklists/requirements.md
```

本 Feature 不涉及新数据实体或外部接口，因此不创建 `data-model.md` 和 `contracts/`。

## 源代码结构

```text
frontend/src/components/UploadTaskEditor.tsx
frontend/src/components/MaterialStatesEditor.tsx
frontend/src/components/PropertyModuleEditor.tsx
frontend/src/components/SchemaDrivenRecordForm.tsx
tests/01_decentralized_uploading/material-states-editor.test.tsx
tests/01_decentralized_uploading/property-record-editor.test.tsx
tests/01_decentralized_uploading/upload-task-editor-layout.test.tsx
```

**结构选择**：`UploadTaskEditor` 继续拥有完整草稿和保存生命周期；`MaterialStatesEditor` 负责材料状态集合；新增的卡片边界只负责单状态展示与事件转发；`PropertyModuleEditor` 和 `SchemaDrivenRecordForm` 继续分别负责模块/定义选择和 Schema 字段。这样不复制数据规则，也不改变提交链路。

## 需求到设计的映射

| 来源 | 设计组件/接口 | 验证方式 |
|------|---------------|----------|
| FR-001 / US1 | `MaterialStateCard` 记忆化边界，未变化状态引用跳过渲染 | 材料状态渲染计数测试 |
| FR-002 / US1 | 空间群 Autocomplete 本地 `inputValue`，提交时调用状态更新 | 空间群输入/选择测试 |
| FR-003 / US1、US2 | `useMemo` 缓存选项、Schema 和校验结果 | 多状态与多记录定向测试 |
| FR-004 / US2 | 定义绑定按 record key、版本和定义身份去重 | 定义请求与绑定测试 |
| FR-005 / US3 | 保留 `UploadTaskEditor` 保存、提交和错误定位逻辑 | 上传编辑器回归与构建 |

## 阶段与依赖

1. 先增加渲染范围和输入行为的失败回归测试（T001–T003）。
2. 实施材料状态卡片隔离、空间群本地输入和选项缓存（T004–T006）。
3. 实施动态记录定义绑定与 Schema/校验缓存（T007–T008）。
4. 运行定向回归、构建、文档检查，更新 Overview 和 Issue（T009–T011）。

## 复杂度说明

| 必要复杂度 | 为什么需要 | 已拒绝的简单方案及原因 |
|------------|------------|--------------------------|
| 材料状态卡片组件边界 | 只有真实的组件边界才能阻止未修改卡片执行 JSX 和 MUI 树渲染 | 仅在父组件加 `useMemo` 仍会因整个 `states` 数组变化而失效 |
| 空间群本地输入 | 受控父级每字符更新是自由输入卡顿的直接来源 | 只增加 `useMemo` 不能消除每字符状态传播 |
# 2026-09-10 局部修复计划

[Issue #102](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/102) 保持本 Plan 的状态所有权：`elementCountEdits[index]` 仍是 `MaterialStatesEditor` 的会话内状态，作为对应卡片缓存的必要输入。FR-001、FR-005 由新增 T012–T014 覆盖，验证非法值提示、草稿原值保存及其他四张卡片渲染计数不增加。
