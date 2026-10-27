# 实施任务

输入：[spec.md](spec.md)、[plan.md](plan.md)、[research.md](research.md)、[data-model.md](data-model.md)、[接口](contracts/results.md)。

- [x] T001 在 docs/specs/164-dos-relative-normalization/ 落地已确认文档与原图索引；检查 FR/SC 覆盖。
- [x] T002 [US1] [US2] [US3] 在 backend/tests/test_spectra_dos_relative.py 建立科学数值与条件边界测试。
- [x] T003 [US1] [US2] [US3] [US4] 实现 backend/spectra/dos.py、context.py、contracts.py、discovery.py 并接入 recalculate.py/engine.py。
- [x] T004 [US1] [US2] [US3] [US4] 在 frontend/src/components/spectrumEditor/DosRelativeMetrics.tsx 和 SpectrumDetailView.tsx 展示并切换；新增组件测试。
- [x] T005 [US3] 在 backend/services/spectra.py 核对公开过滤，在后端测试验证新版本、旧记录、人工保存失效和权限。
- [x] T006 [US1] [US2] [US3] [US4] 在 tests/01_decentralized_uploading/ 添加隔离浏览器验收，运行回归与构建，记录 validation.md。
- [x] T007 使用 Overview 技能更新 docs/overview/01_Decentralized_Uploading_of_Superconductivity_Data/data-structure-and-form-mapping.md；更新 Issue 进展；提交结果记录在最终交付说明。

依赖按 T001→T002→T003→T004→T005→T006→T007 串行执行。覆盖映射见 plan.md。先实现独立面积，再增加比例/共同归一化，最后确认原有绝对模式和 α²F 回归。

验证依据：T002–T006 见 [validation.md](validation.md) 的 SC 映射、194 项后端/45 项前端及浏览器报告。T007 的 Overview 已按实际代码回写；远程文档链接门仍未完成。
