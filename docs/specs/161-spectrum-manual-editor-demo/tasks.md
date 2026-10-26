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

## 二维拖动与回折修正

- [x] T013 只读核对已保存数据，归档三张截图、用户原话和诊断，更新 Issue/Spec。
- [x] T014 实现描线顺序、几何插点、默认二维及可撤销重新连线，保持旧坐标与草稿。
- [x] T015 验证截图日志回归、二维越过、旧草稿、撤销/保存、既有交互及性能，记录后本地提交。

二维修订证据：28项逻辑测试、34个浏览器场景、真实草稿副本及截图日志回归、构建通过；原浏览器保存键前后哈希相同。详见 xy-validation.md。

## 坐标读数与轴叠加

- [x] T016 追加用户原话、识别刻度来源与边界，更新 Issue/Spec。
- [x] T017 实现新增点自动选中、右侧读数、零频线坐标与状态说明。
- [x] T018 实现当前轴/识别刻度/λ参照/投影辅助线，共用坐标变换并兼容旧草稿。
- [x] T019 完成逻辑、浏览器、缩放单位轴向、窄屏和历史回归，记录后提交。

坐标/轴叠加证据：35项逻辑测试、43个浏览器场景、TypeScript/Vite构建；见 axes-validation.md。

## 三邻点与调参位置

- [x] T020 将主影响区改为各3点，集中源码配置并同步界面；验证默认和手工参数，记录位置及结果后提交。

本轮38项逻辑测试、43个真实浏览器场景和构建通过；手工参数测试覆盖比例、衰减长度、截断及非法值。证据见 influence-validation.md。
