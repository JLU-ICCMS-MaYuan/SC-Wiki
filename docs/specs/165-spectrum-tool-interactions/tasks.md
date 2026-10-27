# 实施任务

**输入**：[spec.md](spec.md)、[plan.md](plan.md)、[research.md](research.md)、[data-model.md](data-model.md)、[交互契约](contracts/interactions.md)。
本轮只完成T001；以下未勾选项为后续实施任务，不代表代码已实现。

## 准备与基础

- [x] T001 在 docs/specs/165-spectrum-tool-interactions/ 保存完整原话、澄清、确认后的需求与设计，完成文档一致性检查；证据见 analysis.md。
- [ ] T002 [US3] 在 tests/01_decentralized_uploading/spectrum-tool-interactions.test.tsx 先覆盖默认idle、同钮退出、异钮切换、Esc与立即动作边界。
- [ ] T003 [US3] 在 frontend/src/components/spectrumEditor/SpectrumManualEditor.tsx 和 SourceCanvas.tsx 统一工具身份与退出清理，包括标定槽身份、手势预览及失效锚点。

## US1：两个并列拖动按钮

- [ ] T004 [US1] 在 tests/01_decentralized_uploading/spectrum-tool-interactions.test.tsx 验证单点不牵连与联动保持，随后在 frontend/src/components/spectrumEditor/SpectrumManualEditor.tsx、frontend/src/components/spectrumEditor/SourceCanvas.tsx 拆分两个按钮并移除重复开关；不修改 dragInfluence.ts。

## US2：先选工具再选起点

- [ ] T005 [US2] 在 tests/01_decentralized_uploading/spectrum-tool-interactions.test.tsx 覆盖无选点/多选/唯一点、首次不改数据、无候选、跨分波、缩放及重新进入。
- [ ] T006 [US2] 在 frontend/src/components/spectrumEditor/SpectrumManualEditor.tsx 允许先进入增加点，在 frontend/src/components/spectrumEditor/SourceCanvas.tsx 分离起点选择和新增操作，复用 engine.ts 既有吸附/插点/补接。

## US3：退出与视觉一致

- [ ] T007 [US3] 在 tests/01_decentralized_uploading/spectrum-tool-interactions.test.tsx 覆盖全部持续工具、标定同槽/异槽、退出保留编辑和aria-pressed；核对 frontend/src/components/spectrumEditor/SpectrumManualEditor.tsx 的所有结束回调。
- [ ] T008 [US3] 在 frontend/src/components/spectrumEditor/SpectrumManualEditor.tsx 与 frontend/src/components/spectrumEditor/styles.css 使用主题token实现工具浅/深色、悬停/焦点/禁用；避免全局.active样式影响曲线标签。

## 集成与收尾

- [ ] T009 在 tests/01_decentralized_uploading/spectrum-tool-interactions-production.cjs 使用隔离正式页面验证α²F/DOS、横/纵轴、缩放、窄屏、保存刷新/撤销和颜色计算样式；运行相关回归与前端构建，记录本目录 validation.md。
- [ ] T010 按实际实现更新 docs/overview/01_Decentralized_Uploading_of_Superconductivity_Data/spectrum-manual-editor-demo.md，同步Issue验收与文档影响；远程链接未验证时不关闭Issue。

## 依赖与覆盖

T001→T002→T003；T004、T005/T006、T007/T008共享组件，按顺序执行，最后T009/T010。FR/SC到任务映射见plan.md，测试先于对应实现。MVP先完成统一工具和双按钮，再加入先选工具的加点与主题状态，最终共同验收。
