# 实施计划

Issue：[#166](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/166)。日期：2026-10-27。依据：[spec.md](spec.md)。

## 技术上下文与结构

Python3.12/FastAPI/SQLAlchemy、React19/TypeScript5.6。沿用SpectrumRun JSON及Document.operations，无数据库迁移。
新增backend/spectra/frequency_repair.py：PAVA分块、受限修正、报告与历史判断；recalculate.py在既有精确端点连接之后、诊断和积分之前调用。
新增frontend/src/components/spectrumEditor/frequencyRepairs.ts：解析批次和受保护撤销；SpectrumManualEditor提供操作，SourceCanvas高亮，SpectrumDetailView仅显示未处理原因；公开过滤隐藏内部报告。
pytest检验数学/HTTP/版本，Vitest检验编辑撤销与显示，Playwright使用隔离正式服务验收。

## 质量门与事实来源

mayuan开发，保护已有dragInfluence.ts及Demo；Issue为协作状态，文档远程链接未通过时不关闭。已认可的移动限额与保留幅值/连接为硬约束。实时拖动逻辑不加入优化。算法输入以当前manual_documents与数值曲线匹配为前提，不推测连线或像素。

## 需求到设计与任务映射

| 来源 | 设计/事实来源 | 任务 | 验证 |
|---|---|---|---|
| FR-001/002/003、SC-001 | path_points、原图像素、PAVA冲突块 | T002/T003 | 严格单调/位移/幅值连接不变 |
| FR-004/005、SC-002 | 源图框、零频ID、端点、拓扑检查 | T002/T003 | 超界与固定点不改 |
| FR-006/008、SC-003 | 新run、doc操作、当前版本保护 | T004 | HTTP/重复计算/保存失效 |
| FR-007/008、SC-004 | 批次记录与当前像素校验 | T005/T006 | 组件/浏览器撤销及高亮 |
| FR-009、SC-005 | 线性路径和栈式分块 | T002/T003 | 20,000点实验 |
| SC-006 | 既有测试与公开权限 | T004/T006 | 集成回归 |

## 阶段与复杂度

T001文档→T002测试→T003后端算法→T004重算与存储→T005前端→T006验证→T007文档收尾。
PAVA栈式合并为O(n)，每块只扫描自己的点；记录分片遵守每条操作4000字符/文档4MB和5000操作约束。不为了支持大历史引入新表或另一套保存机制。

## 展示收敛
后续用户要求已处理修正不长期展示：FrequencyRepairReport只渲染skipped原因，SourceCanvas仅编辑模式显示修正点标记。后端计算与保存不变；回归测试覆盖修正后立即显示新结果、刷新/重复重算无清单，进入编辑器仍可撤销。
