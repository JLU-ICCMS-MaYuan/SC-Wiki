# 实施计划：上传校对页全部折叠与展开

**Issue**：[#141](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/141)

**日期**：2026-10-19

**Spec**：[spec.md](spec.md)

## 摘要

复用材料状态的现有按钮，通过局部Context指定顶部Portal槽位；原处理函数同步外层状态及物性区域内的原生details。

## 技术上下文

- 语言：TypeScript ~5.6，React ^19.2，MUI ^7.3，Vite ^5.4。
- 存储：浏览器组件内展示状态，不新增持久化。
- 测试：Vitest ^2.1、Testing Library、jsdom；独立浏览器验证桌面和390px。
- 目标：现有Web上传校对页；线性遍历当前材料状态及四类模块，一次操作完成。
- 约束：mayuan分支；保留已有未提交修改；只提交本次增量，不推送。

## 质量门

| 来源 | 要求 | 方案 | 状态 |
| --- | --- | --- | --- |
| 用户确认 | 两层折叠、顶部入口 | 对照FR及原话 | 通过 |
| AGENTS.md | Issue入口、中文文档 | #141及本目录 | 通过 |
| Spec | 输入保留、范围隔离 | 不卸载、不写业务数据，限制DOM范围 | 通过，见validation.md |
| Git规则 | 不混入已有改动 | 基线备份、增量暂存、独立源码验证 | 通过，独立副本已验证，暂存哈希在提交前核对 |

## 文档结构

本目录包含spec.md、plan.md、research.md、tasks.md、quickstart.md、validation.md、checklists/requirements.md和assets/。不新增业务数据模型及API契约文件，因为业务合同不变；展示交互合同见Spec及本计划。

## 源码结构与职责

- `frontend/src/context/MaterialStateControlsContext.ts`：只传递按钮的顶部容器。
- `frontend/src/pages/UploadPage.tsx`：建立当前任务的容器和布局。
- `frontend/src/components/MaterialStatesEditor.tsx`：复用按钮和局部折叠处理，限制为当前编辑器四类模块。
- `tests/01_decentralized_uploading/upload-expand-collapse-all.test.tsx`：真实材料/模块交互及Portal集成回归。

## 需求到设计和任务映射

| 来源 | 设计与事实来源 | 任务 | 验证 |
| --- | --- | --- | --- |
| FR-001、FR-006 / SC-003 | UploadPage槽位、现有字典 | T002、T004 | 顶部位置、键盘、中英文及窄屏 |
| FR-002、FR-003 / SC-001 | 局部collapsedStates与原生details | T003、T004 | 两材料四类模块全覆盖 |
| FR-004、FR-005 / SC-002 | 既有独立交互及挂载生命周期 | T003、T004 | 重复操作、节点/输入/内部状态保留、无数据写入 |

## 阶段与依赖

T001文档基线 → T002顶部槽位 → T003统一折叠 → T004真实组件及浏览器验证 → T005文档回写及增量提交。

## 复杂度说明

局部Context仅用于跨现有组件层级定位按钮容器，不承载业务状态或新控制协议；复用原生details和已有材料折叠逻辑，遵循KISS、DRY及职责分离。
