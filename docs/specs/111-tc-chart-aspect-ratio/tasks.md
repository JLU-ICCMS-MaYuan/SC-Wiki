# 实施任务：社区 Tc 双图固定 4:3 比例

**输入**：[规格](spec.md)、[计划](plan.md)、[研究](research.md)、[界面契约](contracts/layout.md)。

## 阶段 1：准备

- [x] T001 完成 `docs/specs/111-tc-chart-aspect-ratio/` 规格、研究、契约与需求检查，核对 #111 比例。

## 阶段 2：US1——固定比例与可读布局（P1，完整交付）

独立验收：真实页面五种宽度、桌面侧栏切换、空数据和交互均符合规格。

- [x] T002 [US1] 在 `tests/07_researcher_community_forum/chart-aspect-ratio-browser.mjs` 增加真实浏览器比例、对齐、可读性和交互验收，先确认旧实现失败。
- [x] T003 [US1] 在 `frontend/src/components/ChartScatter.tsx` 实现统一 4:3 绘图容器，移除 `frontend/src/pages/share.tsx` 固定高度调用，并统一加载占位比例。
- [x] T004 [US1] 在 `frontend/src/pages/share.tsx` 与 `frontend/src/components/ChartScatter.tsx` 调整控件、字段提示和图例布局，保证窄屏内容可达。
- [x] T005 [US1] 更新 `tests/07_researcher_community_forum/test_issue30_tc_chart_preferences.py` 受影响的旧尺寸契约；在 `frontend/src/components/ChartScatter.tsx` 修正散点点击绑定，执行现有 `community-charts.test.tsx`、浏览器验收和前端构建。

## 阶段 3：文档与收敛

- [x] T006 更新 `docs/overview/03_Superconductivity_Data_Search_and_Database_Discovery/tc-history-and-pressure-charts.md` 并在 `docs/specs/111-tc-chart-aspect-ratio/validation.md` 记录真实证据，核对需求与链接。

## 依赖与覆盖

顺序为 T001 → T002 的旧实现复现 → T003 → T004 → T005 → T006，T002 在完整浏览器验收通过后勾选。两份源文件共享布局约束，串行修改。

FR-001/FR-002/SC-001 对应 T002/T003；FR-003/SC-002 对应 T002/T004；FR-004/FR-005/SC-003 对应 T002/T005。仅一个用户故事，无单独并行交付项。
