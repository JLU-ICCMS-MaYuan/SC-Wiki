# 实施任务

输入：[spec.md](spec.md)、[plan.md](plan.md)、[research.md](research.md)、[data-model.md](data-model.md)、[contracts/ui.md](contracts/ui.md)。

- [x] T001 回写用户确认、创建实施文档并核对 FR/SC 映射。
- [x] T002 [US1/US2] 在 tests/01_decentralized_uploading/form-contract.test.tsx 增加四宿主渲染、字段独立与正确性失败测试，补标记拓扑回归；首次 11 项失败及追加读取／删除失败均已复现。
- [x] T003 [US1/US2] 修改 MaterialStatesEditor.tsx、EvidenceFieldMarkers.tsx、EvidenceWorkflow.tsx、PropertySpectra.tsx，修复实际依赖更新并保留最新回调。
- [x] T004 [US1/US2] 本地门禁 62 项和构建通过，大草稿扫描 22→0；原有 19 项失败与独立基线一致，证据见 validation.md。
- [x] T005 [US3] npm、scripts/check-form-contract.mjs、CI 工作流及 AGENTS.md 约束已加入；注入旧缺陷被四宿主 8 项断言检出。只验证本地相同命令，不宣称远端 CI 已运行。
- [x] T006 [US3] 完善全站入口的数据归属和触发说明，回写 Overview/README、检查表和 Issue，按明确范围自动提交；其他页面未验收与远程链接未验证明确保留。

按 T001→T002→T003→T004→T005→T006 执行；共享文件串行，不使用子代理。技术任务完成不代表远程链接或部署完成。
