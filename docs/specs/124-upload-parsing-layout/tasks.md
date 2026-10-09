# 实施任务：PDF 解析详情紧凑布局

**输入**：[spec.md](spec.md)、[plan.md](plan.md)、[research.md](research.md)、[contracts/sticky-layout.md](contracts/sticky-layout.md)

## 阶段 1：准备

- [x] T001 确认 `frontend/src/pages/UploadPage.tsx`、`frontend/src/components/AppShell.tsx` 和 `tests/01_decentralized_uploading/upload-task-workspace.test.tsx` 的现有布局与交互。

## 阶段 2：用户故事 1——紧凑且完整的解析工作区（P1）

**目标**：展开解析时让常驻栏遮挡连续、操作可达，左右只留窄缝。

**独立验收**：按 [quickstart.md](quickstart.md) 检查桌面和窄屏滚动与收起。

- [x] T002 [US1] 调整 `frontend/src/pages/UploadPage.tsx` 的展开态边距和常驻栏样式，覆盖 FR-001 至 FR-004。
- [x] T003 [US1] 更新并运行 `tests/01_decentralized_uploading/upload-task-workspace.test.tsx` 的原有常驻栏回归断言，覆盖 FR-005。

## 最终阶段：验证与当前事实回写

- [x] T004 运行 `frontend/package.json` 的构建并按 `docs/specs/124-upload-parsing-layout/quickstart.md` 核验实际布局。
- [x] T005 完成后更新 `docs/overview/01_Decentralized_Uploading_of_Superconductivity_Data/README.md`，记录已落地的布局行为。

## 依赖与执行顺序

- T001 完成后实施 T002；T003 验证 T002；T004 在样式与回归验证后执行；T005 仅在行为已落地后执行。
- 全部任务在同一页面路径上串行推进，无并行工作。

## 需求覆盖

| 来源 | 任务 | 说明 |
|------|------|------|
| FR-001、FR-002、SC-001 / US1 | T002、T004 | 栏高、顶部遮挡、可读性 |
| FR-003、SC-002 / US1 | T002、T004 | 展开边距及收起恢复 |
| FR-004、SC-003 / US1 | T002、T004 | 窄屏无溢出与按钮可达 |
| FR-005、SC-004 / US1 | T003、T004 | 任务切换与草稿保留 |
