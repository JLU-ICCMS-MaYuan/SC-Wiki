# 实施任务：上传解析记录表单性能修复

**输入**：[spec.md](spec.md)、[plan.md](plan.md)、[research.md](research.md)、[quickstart.md](quickstart.md)

## 阶段 1：准备与失败测试

- [x] T001 [US1] 增加材料状态渲染计数回归测试，证明修改一个状态时其他状态不重新渲染（`upload-form-performance.test.tsx`）。
- [x] T002 [US1] 增加空间群自由输入和候选选择测试，证明输入不逐字符更新父级草稿且提交值准确（`upload-form-performance.test.tsx`）。
- [x] T003 [US2] 增加多记录渲染计数和定义请求去重回归测试（`upload-form-performance.test.tsx`）。

## 阶段 2：材料状态编辑优化

- [x] T004 [US1] 在 `MaterialStatesEditor.tsx` 复用未修改材料状态卡片，保留状态更新、折叠、错误和结构候选行为。
- [x] T005 [US1] 在 `MaterialStatesEditor.tsx` 为空间群 Autocomplete 增加本地输入状态，处理候选选择、清空和失焦提交。
- [x] T006 [US1] 在 `MaterialStatesEditor.tsx` 缓存空间群选项、状态候选和能量高于 Hull 判定，避免无关渲染重复计算。

## 阶段 3：动态物性记录优化

- [x] T007 [US2] 在 `PropertyModuleEditor.tsx` 增加记忆化记录边界，保证未修改记录引用不触发重新渲染。
- [x] T008 [US2] 抑制定义身份未变化时的绑定状态重复写入，并在 `SchemaDrivenRecordForm.tsx` 缓存有效 Schema 和客户端校验结果。

## 最终阶段：验证与文档

- [x] T009 [US3] 运行上传相关 Vitest、TypeScript 检查和前端生产构建，确认本 Feature 无回归。
- [x] T010 [US3] 使用 Overview 维护流程更新 `docs/overview/01_Decentralized_Uploading_of_Superconductivity_Data/data-structure-and-form-mapping.md`，记录渲染隔离和输入提交约束。
- [x] T011 [US3] 回写 Issue #96 的 Spec 链接、实现摘要、验证结果和 Documentation Impact，完成关闭检查并关闭 Issue。

## 依赖与执行顺序

- T001–T003 必须先于对应实现任务；测试先红后绿。
- T004–T006 共享 `MaterialStatesEditor.tsx`，按顺序串行。
- T007–T008 共享动态记录组件，按顺序串行。
- T009 依赖所有代码任务；T010–T011 依赖验证通过。

## 需求覆盖

| 来源 | 任务 | 说明 |
|------|------|------|
| FR-001 / US1 / SC-001 | T001、T004 | 材料状态组件按对象引用隔离渲染 |
| FR-002 / US1 / SC-003 | T002、T005 | 空间群输入本地化并在提交点更新草稿 |
| FR-003 / US1、US2 / SC-002 | T006、T008 | 缓存选项、Schema 和校验计算 |
| FR-004 / US2 / SC-002 | T003、T007、T008 | 记录边界和定义绑定去重 |
| FR-005 / US3 / SC-004 | T009、T010、T011 | 保存、提交、文档和 Issue 收尾 |

## MVP 与增量策略

1. 先完成材料状态卡片和空间群输入优化，恢复主要用户路径。
2. 再完成动态物性记录隔离和 Schema/定义缓存。
3. 最后运行全量相关验证并完成文档、Issue 和 Git 提交。
