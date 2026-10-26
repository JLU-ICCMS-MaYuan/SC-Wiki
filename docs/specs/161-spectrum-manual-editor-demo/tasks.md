# 实施任务

Issue [#161](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/161) 是协作状态来源，本文仅为技术拆解。

- [x] T001 创建 spec.md、plan.md、research.md、data-model.md、contracts/demo.md、assets/images.json 与覆盖映射；校验原话、最新取舍和范围。FR-001 至 013；IMG-001 缺失明确记录，不宣称完整归档。
- [x] T002 在 demo/scripts/prepare-fixtures.py、demo/src/fixtures.json 准备真实来源图与固定示例；assets/fixtures.json 记录来源哈希、取样及注入错误。FR-004、007、012、013。
- [x] T003 在 demo/src/engine.ts 实现轴映射、片段、受约束联动、操作历史；demo/tests/engine.test.ts 的 19 项逻辑测试通过。US1/2/3/4；SC-002/003/004/005。
- [x] T004 在 demo/src/SourceCanvas.tsx 实现来源图缩放、平移、固定命中、拖动、框选、补点与标零；实际浏览器鼠标操作证据见 assets/browser-validation.json。US1/2/3；SC-001/002/003/004。
- [x] T005 在 demo/src/App.tsx、demo/src/styles.css 实现详情/编辑器、坐标表单、分波切换、图表同步及窄屏样式；截图及操作记录见 assets/。US1/2/3；SC-001/002/006。
- [x] T006 在 demo/src/App.tsx 实现显式本机保存、恢复、损坏/失败提示和未保存退出保护；浏览器真实 Storage 异常和刷新恢复通过。US4；SC-005。
- [x] T007 完成类型检查与独立构建，demo/tests/browser.cjs 中 25 个全流程、桌面/窄屏场景通过；validation.md 与 assets/browser-validation.json 记录截图、网络与失败证据。SC-001 至 007。
- [x] T008 对照全部原文复核，更新文档与 Issue #161 的完成记录；本次文件精确纳入本地提交，提交身份见 Git 历史，不推送，远程链接仍待验证。工作区中其他任务的 #162 文件不属于提交范围。

## 覆盖与收尾边界

需求、设计、任务、验证的完整映射见 plan.md；结果见 validation.md。所有 P1 用户故事均在隔离 Demo 路径验证，未替代正式业务路径验收。远程 Spec 链接及用户试用认可仍保持未完成。

## 本轮迭代

- [x] T009 保存新原话和 IMG-003，更新 Issue、Spec、设计契约。
- [x] T010 实现人工补点邻接连线、删除断边、旧草稿兼容与回归。FR-014 / SC-008。
- [x] T011 实现各侧5点核心、指数尾部、准备结果复用及界面说明。FR-015、016 / SC-009、010。
- [x] T012 完成单元、浏览器、10000点核心计时和构建，记录证据并提交。

本轮证据：23 项逻辑测试、30 个浏览器场景、独立构建；详见 iteration-validation.md。
