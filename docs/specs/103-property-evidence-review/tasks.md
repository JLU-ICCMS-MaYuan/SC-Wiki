# 技术任务

## 2026-09-17 整合收尾

用户本轮授权审计并提交 #100 至 #106，另明确允许单独提交 #103 必需的 Tc 依赖。
前轮仅允许提交当轮差量，所以下文保留的“未提交/阻塞”段落属于历史记录；本轮改为先提交
Tc 依赖、再整合 #103，排除 #94 自定义模块定义及其迁移。各阶段提交收尾由 T061 统一完成。

- [x] T061 核验已有实现，修复旧测试契约，验证排除无关改动的候选提交树，分批回写 Overview 并提交；保留未推送和未执行新部署的边界。[SC-001～027]

## 结构区紧凑与折叠

- [x] T058 合并本次六项反馈到原 Issue/Spec 与实施方案，保留前轮需求。[FR-039/040]
- [x] T059 实现共享固定尺寸结构视图、移除底部图例及独立附件折叠，保留当前选择和核对入口。[SC-026/027]
- [x] T060 通过组件/双入口浏览器/构建验证，回写文档和 Issue，检查仅本次差量的提交边界。

T060 的验证与文档已完成；本轮差量依赖开工前未跟踪的 `CrystalStructureView.tsx` 和已有未提交区块，
仅含 HEAD 的临时 index 无法应用，因此不暂存、不扩大范围提交。详细验收与隔离检查见 [验证路径](quickstart.md#结构附件紧凑与独立折叠2026-09-17)。

## 统一字段与晶体结构展示（2026-09-17）

- [x] T053 记录用户确认的 Demo 和结构左右布局，更新 Issue、Spec、Plan 与验收映射。[FR-035—038]
- [x] T054 接入共享研究材料摘要、关系编辑与状态类型，验证保存、重载和来源保留。[SC-023]
- [x] T055 实现同一解析模型的三维、参数、矩阵与原子位置展示，覆盖晶胞、格式切换和窄屏。[SC-024]
- [x] T056 补齐字段及结构稳定核对位置，移除页尾原始数据兜底，保留紧凑未定位入口。[SC-025]
- [x] T057 完成组件、存储链路、浏览器与构建验证，回写 Overview/Issue 并检查隔离提交。

T053—056 已在当前工作树实现并验证；T057 的验证与文档回写完成，但独立提交无法安全分离，
保留未勾选。未暂存或提交已有审核代码，也未切换分支、推送或部署。证据和提交检查见 [验证路径](quickstart.md#正式统一布局与结构左右展示2026-09-17)。

按顺序实施，Issue 是协作状态来源。基础服务完成后接入 US1/US2，US3 验证两条流程。

- [x] T001 核验全部需求、设计、接口、任务和验证映射，docs/specs/103-property-evidence-review/
- [x] T002 [US1] 建立定位、多证据与同键隔离回归，tests/01_decentralized_uploading/test_property_evidence.py
- [x] T003 [US1] 修复证据转换与落库，backend/ingest/scientific_drafts.py、backend/api/rag.py、frontend/src/lib/propertyModules.ts
- [x] T004 新增模型与迁移，backend/models.py、alembic/versions/
- [x] T005 [US1] 实现共享核对服务与后台接口，backend/ingest/property_evidence.py、backend/api/evidence.py
- [x] T006 [US1] 接入上传事务与锁，backend/api/rag.py
- [x] T007 [US2] 接入审核事务、人工历史与删除生命周期，goserver/handlers/paper_evidence.go
- [x] T008 [US3] 建立前端状态机回归，tests/01_decentralized_uploading/evidence-workflow.test.tsx
- [x] T009 [US1] [US2] [US3] 共享组件与三个入口，frontend/src/components/EvidenceWorkflow.tsx、UploadTaskEditor.tsx、frontend/src/pages/AdminPage.tsx、AdminPaperEditPage.tsx
- [x] T010 [US1] [US2] 真实 MySQL 与 #29 验证，tests/01_decentralized_uploading/test_property_evidence_mysql.py、goserver/handlers/paper_evidence_mysql_test.go
- [x] T011 [US3] 浏览器验收、针对性回归与构建，docs/specs/103-property-evidence-review/quickstart.md
- [x] T012 回写 Overview、Issue 并规范提交，docs/overview/

验收证据及运行方式见 [验证路径](quickstart.md)。当前功能说明从 [Overview](../../overview/README.md) 导航；Issue 保有协作状态，本文不作为发布状态副本。

- [x] T013 [US1] [US2] 去除手动选片段和编辑引句，自动复用找到的证据；重试真正重查未解决记录；同步可读提示、回归和真实页面验收，并回写文档与 Issue。[FR-009 / SC-004]
- [x] T014 [US3] 为后台核对提供真实批次计数、进度条、阶段与等待计时；验证排队、进行中、取消及完成，回写接口、验收与 Overview。[FR-010 / SC-005]
- [x] T015 [US1] 上传疑点返回时自动保存已找到证据到 Redis 草稿，保留完成任务并在下次复用；验证返回、重载、提交入库与无重复 LLM。[FR-009 / SC-006]

## 第二阶段收敛 — 2026-09-15 全科学数据与持久审核

旧 T009/T015 不能证明本轮抽屉和持久恢复完成；下列任务覆盖新增及原路径缺失。

- [x] T016 完成已确认 Issue/Spec、设计、契约与需求映射，docs/specs/103-property-evidence-review/。[FR-011—017]
- [x] T017 [US1] [US3] 建立科学项、持久化、失效与来源行为回归，tests/01_decentralized_uploading/test_scientific_evidence.py。[FR-011/013/017]
- [x] T018 [US1] [US4] 实现全科学数据快照、来源验证、结构提交者及持久模型迁移，backend/ingest/property_evidence.py、backend/ingest/scientific_evidence.py、backend/models.py、alembic/versions/。[FR-011/014]
- [x] T019 [US1] [US3] 接入后台持久保存、恢复、按项重试、裁决草稿与上传生命周期转接，backend/api/evidence.py、backend/api/rag.py、backend/ingest/upload_tasks.py。[FR-013/015/017]
- [x] T020 [US2] [US4] 实现全项批准事务、永久出处与 RAG 来源归因，goserver/handlers/paper_evidence.go、goserver/handlers/admin.go、backend/api/rag.py、backend/rag/。[FR-014/015/016]
- [x] T021 [US2] [US3] 建立共享右侧抽屉与字段标记行为回归，tests/01_decentralized_uploading/evidence-workflow.test.tsx。[FR-012]
- [x] T022 [US1] [US2] 实现共享字段标记、抽屉、恢复、保存后批准与三入口接入，frontend/src/components/EvidenceWorkflow.tsx、frontend/src/components/MaterialStatesEditor.tsx、frontend/src/components/SchemaDrivenRecordForm.tsx、frontend/src/components/UploadTaskEditor.tsx、frontend/src/pages/AdminPaperEditPage.tsx、frontend/src/pages/AdminPage.tsx。[FR-012/015]
- [x] T023 [US1] [US2] [US3] [US4] 完成真实 MySQL/RQ、浏览器、RAG、权限与事务回归及构建，tests/01_decentralized_uploading/、goserver/handlers/paper_evidence_mysql_test.go、docs/specs/103-property-evidence-review/quickstart.md。[SC-001—010]
- [x] T024 验收后回写当前功能 Overview、Issue 与规范提交，docs/overview/。[FR-011—017]

依赖：T016 → T017 → T018 → T019 → T020 → T021 → T022 → T023 → T024。同文件串行；完整验收后才勾选。US1 单独验收上传恢复；US2 单独验收批准事务；US3 验收取消与跨进程恢复；US4 验收结构出处及 RAG 限定。不以部分功能作为本轮完成。

T024 的 Overview、README 和 Issue 同步已完成；Git 提交因原有未提交修改与本轮实现处于相同代码区块，无法在保留独立范围的同时形成完整可验证提交而暂停。依据用户明确要求未暂存、未提交；具体校验与实际验收边界见 [验证路径](quickstart.md)。

## 阶段四：红点与可编辑建议收敛

- [x] T025 [US2] 更新已确认需求及接口并通过一致性门，docs/specs/103-property-evidence-review/。[FR-018—022]
- [x] T026 [US2] 聚合同框标记与键盘入口，frontend/src/components/EvidenceFieldMarkers.tsx；新增行为回归。[FR-018 / SC-011]
- [x] T027 [US1] 实现有来源的类型化建议及按用户持久草稿，backend/ingest/evidence_proposals.py、backend/api/evidence.py。[FR-019/020/022 / SC-012]
- [x] T028 [US2] 实现准备补丁、两段保存与精确绑定，frontend/src/components/EvidenceWorkflow.tsx、frontend/src/pages/AdminPaperEditPage.tsx、backend/ingest/evidence_proposals.py。[FR-020/022 / SC-012]
- [x] T029 [US1] [US2] 接入共享抽屉与三个独立审核入口，frontend/src/components/UploadTaskEditor.tsx、frontend/src/pages/AdminPage.tsx、frontend/src/pages/AdminPaperEditPage.tsx。[FR-019/021 / SC-013]
- [x] T030 [US1] [US2] 运行针对性 Python/Go/Vitest/构建、真实 MySQL 回滚和浏览器验收，tests/01_decentralized_uploading/、goserver/handlers/。[SC-011—013]
- [x] T031 验收后回写 Overview、Issue 与隔离提交，docs/overview/；保留 T024 阻塞记录。[FR-018—022]

依赖：T025 → T026 → T027 → T028 → T029 → T030 → T031；同文件串行。所有用户故事均验收持久恢复和独立提交；不以旧任务勾选替代新流程证据。

T026—T030 的实现与验收依据见 quickstart.md 本轮结果。T031 的 Overview、README 与 Issue 已同步；独立提交因前序未提交依赖及同块重叠无法安全分离，保持未勾选，不扩大暂存范围。

## 阶段五：说明文字入口

- [x] T032 [US1] [US2] 以现有字段标签/区域标题替代红点，保留聚合、键盘和焦点返回；验证共享表单与快速审核，回写当前说明。frontend/src/components/EvidenceFieldMarkers.tsx、tests/01_decentralized_uploading/scientific-evidence-markers.test.tsx。[FR-018 / SC-011]

T032 依赖 T026；接口和数据模型不变。T024/T031 原提交隔离阻塞保持。

## 阶段六：人工确认与可靠即时保存

- [x] T033 更新人工裁决范围、状态与保存规则，建立 FR-023—025 / SC-014—015 映射并通过一致性检查。
- [x] T034 实现未核对草稿、人工版本决定、派生依赖、Go 放行及 RAG 人工归因，并增加真实 MySQL 回滚回归。
- [x] T035 共享前端合并保存、失败暂停与手动重试，未核对展示和管理员人工完成入口，增加行为回归。
- [x] T036 验证 Python/Go/Vitest/构建/浏览器，补齐 #29 核对并保留接受草稿，不实际批准。
- [x] T037 验证后回写 Overview/Issue 并检查提交隔离；保留 T024/T031 原阻塞。

依赖 T033 → T034 → T035 → T036 → T037；不新增基础设施，不切换分支或推送。

T033—T036 已实现验证；T037 的 Overview/README/Issue 同步完成，提交隔离仍阻塞：独立补丁无法应用到 HEAD，且共享科学核对模块/测试不在原 index。未暂存、提交、切换分支或推送。

## 阶段七：审核区域随页面滚动

- [x] T038 [US2] 取消已接受建议列表与审核操作区吸顶，验证滚动后不遮挡表单并同步当前行为。[FR-021]

需求、方案、组件职责与验证一致；本项仅调整布局，接口和数据模型不变。

T038 验证：现有编辑页 9 项 Vitest 通过；Chromium 使用当前前端与隔离 API 夹具验证管理员和超级管理员滚动，审核区域为正常文档流，不遮挡后续表单。未请求模型或实际批准。

## 阶段八：压强编辑与人工确认闭环

- [x] T039 [US2] 增加真实输入、整组清空及修改后确认回归，tests/01_decentralized_uploading/pressure-review-editing.test.tsx。[FR-026—028 / SC-016/017]
- [x] T040 [US1] [US2] 实现压强临时输入、原始条件及字段通知，frontend/src/components/MaterialStatesEditor.tsx、PressureEditor.tsx、EvidenceFieldMarkers.tsx；backend/ingest/upload_jobs.py 保留显式清空。[FR-026]
- [x] T041 [US2] 实现当前值读取、保存后刷新、理由和异步版本隔离，frontend/src/components/EvidenceWorkflow.tsx、frontend/src/pages/AdminPaperEditPage.tsx。[FR-027/028]
- [x] T042 [US2] 隔离旧版本接受草稿，保留原判断和历史，backend/ingest/scientific_evidence.py、backend/ingest/evidence_proposals.py。[FR-027]
- [x] T043 [US2] 验证浏览器、存储与构建并同步 Overview/Issue，检查隔离提交，docs/specs/103-property-evidence-review/quickstart.md。[SC-016/017]

T039—T042 已通过真实浏览器、45 项 Python（含当前 MySQL 外层回滚）、114 项不同 Vitest、Go handlers 与前端构建验证。T043 的代码验收与文档回写完成，提交部分仍受前序未提交依赖及同块重叠阻塞：本次独立补丁在仅含 HEAD 的临时 index 上无法应用，不扩大暂存范围。具体测试边界与既有两项上传测试失配见 [验证路径](quickstart.md)。

## 阶段九：材料名与公共保存错误

T044—046 对应 [缺列修复](material-name-migration-fix.md)，T047—049 对应 [材料名保存闭环](material-name-save-flow.md)。后者补足空公式、单字段更新遗漏、结构家族保留、当前版本理由和删除项重查；任务状态及真实验收证据以对应记录为准，不以旧核对任务已完成代替本轮验收。

## 阶段十：完成后自动关闭与保持阅读位置

- [x] T050 [US2] 复现并修复共享侧栏成功关闭、原字段焦点及布局位移，覆盖失败、分组、迟到响应和浏览器滚动，frontend/src/components/EvidenceWorkflow.tsx、tests/01_decentralized_uploading/evidence-drawer-close.test.tsx、evidence-drawer-browser.mjs。[FR-033 / SC-021]
- [x] T051 验证后同步 Spec、Overview 和 Issue #103，并检查独立提交范围；保留前序未提交依赖。[FR-033 / SC-021]

T050：54 项前端回归、TypeScript/Vite 构建通过，三组隔离浏览器脚本均覆盖两角色。T051 的文档已回写，提交隔离结果见 [验证路径](quickstart.md)。

## 阶段十一：红框不压文字

- [x] T052 [US1] [US2] 在 tests/01_decentralized_uploading/scientific-evidence-markers.test.tsx 和 evidence-border-browser.mjs 复现标签被边线穿过，修复 frontend/src/components/EvidenceFieldMarkers.tsx，验证各控件、主题和交互，并同步本 Spec、Overview 与 Issue #103。[FR-034 / SC-022]

只改共享红框呈现，不改科学数据或核对接口；前序提交隔离阻塞单独保留。
