# 实施任务

输入：[Spec](spec.md)、[Plan](plan.md)、[Research](research.md)、[契约](contracts/record-form.md)。

- [x] T001 建立 docs/specs/94-property-record-editor/ 全部产物，核对旧数据、Schema 和提取路径。
- [x] T002 [US1] 在 frontend/src/components/PropertyModuleEditor.tsx 移除标签版本后缀；在 tests/01_decentralized_uploading/property-record-editor.test.tsx 固定显示和内部版本断言。
- [x] T003 [US2] 在 frontend/src/components/SchemaDrivenRecordForm.tsx 实现实验条件单框与旧对象投影，前端交互测试覆盖保留旧值、Evidence 与换行。
- [x] T004 [US2] 修改 backend/ingest/upload_jobs.py 两阶段 prompt；在 backend/ingest/property_modules.py、frontend/src/lib/formDefinitions.ts 校验文本类型，并在 backend/tests/test_property_record_conditions.py 验证真实归一化和持久化往返。
- [x] T005 [US3] 在 frontend/src/components/PropertyModuleEditor.tsx 增加独立记录折叠；前端测试覆盖多条记录、编辑、复制、删除、只读与错误摘要。
- [x] T006 运行定向及共享表单回归、TypeScript 编译，使用 Overview Skill 更新 docs/overview/01_Decentralized_Uploading_of_Superconductivity_Data/ 下表单映射和解析流程文档，回写 Issue 并提交明确文件。

## 依赖与验收

T001 是文档门；T002～T005 的测试先于对应实现。T002 与 T005 共享文件串行处理，T003/T004 的描述字段约定一致后联调。
T006 依赖其余任务全部验证通过。三个故事均属最小交付，独立验收见 Plan 映射。

## Tc 紧凑布局增量（US4）

以下 T007/T008 描述的是当时通过的旧交互；原始记录设计已由用户最新澄清及 T012～T014 取代。

- [x] T007 [US4] 在 tests/01_decentralized_uploading/tc-record-layout.test.tsx 建立真实输入、原始值保留、范围与只读回归（FR-007～011）。
- [x] T008 [US4] 在 frontend/src/components/TcRecordFields.tsx 与 SchemaDrivenRecordForm.tsx 实现紧凑行及原始记录折叠（FR-007、008）。
- [x] T009 [US4] 在 frontend/src/lib/formDefinitions.ts、UploadTaskEditor.tsx、AdminPaperEditPage.tsx 接入保存前 Tc 校验；PropertyModuleEditor.tsx 使用规范值摘要（FR-009、010）。
- [x] T010 [US4] 在 tests/01_decentralized_uploading/tc-record-browser.mjs 验证布局、保存重载与 #103 核对定位；运行现有共享回归、后端、TypeScript 与构建（SC-004～006）。
- [x] T011 [US4] 更新本目录 quickstart.md、功能总览及 Issue #94；核验可安全分离的提交范围并提交（FR-011）。

T011 的文档与 Issue 回写已完成；提交未完成。当前 HEAD 已引用尚未提交的 evidenceFields、
evidenceProposals、PressureEditor、EvidenceFieldMarkers，且旧 EvidenceWorkflow 接口与调用方
不匹配。仅加入本次增量的隔离副本无法构建，不能混入前序 #103 修改后声称是独立提交。
完整工作树的行为与构建验证见 quickstart；实际 Git index 保持未暂存。

## 用户澄清：当前 Tc 为唯一数据（US4）

- [x] T012 [US4] 更新 tests/01_decentralized_uploading/tc-record-layout.test.tsx 和 test_tc_record_roundtrip.py，先复现原始记录多余、旧值残留及隐藏必填问题（FR-008、009）。
- [x] T013 [US4] 在 TcRecordFields.tsx、SchemaDrivenRecordForm.tsx、propertyModules.ts、formDefinitions.ts 及 backend/ingest/property_modules.py 删除双值交互并统一当前 Tc 表示，保留核对定位与类型校验（FR-008～011）。
- [x] T014 [US4] 更新 tc-record-browser.mjs，验证上传/管理员/只读、新建、清空、范围、保存重载及当前核对，更新本 Spec、Overview、Issue #94 并复查提交边界（SC-004～006）。

T013 同时覆盖 EvidenceFieldMarkers.tsx 的旧字段定位、evidenceProposals.ts 的当前值同步，
以及 backend/ingest/evidence_proposals.py 的候选字段与精确内容确认。验证证据见 quickstart。
T014 已完成本轮验收及边界复查，不代表 T011 的独立提交已完成。

## 2026-09-17 必需依赖收尾

以上提交阻塞为前轮记录。用户在 #100 至 #106 整合审计中明确授权提交 #103 必需的 Tc
依赖；T011 按此授权收尾。Tc 规范化、紧凑输入和保存校验独立成批，核对集成及相应测试随
#103 下一批提交。应用级验收以两批合并后的候选树为准，不把 Tc 依赖批次称为独立完整应用。
本轮不提交自定义模块定义和 `20260914_0052` 迁移，也不据此宣称整个 #94 已关闭或上线。

## 2026-10-15 配对单行（US5）

- [x] T015 [US5] 留存完整用户原话、两张图片与最终 Demo，补齐 Spec/Plan/Research/契约并同步 Issue #94（FR-012～017）。
- [x] T016 [US5] 实现前置参数、单行及无边框同色 Tc/μ* 分组，移除重复通用参数入口（FR-012～014、017）。
- [x] T017 [US5] 实现配对归一化、旧参数读取和无损更新，前后端校验与类型切换（FR-015、016）。
- [x] T018 [US5] 验证真实输入、范围交换、清空零值、非法输入、隔离 SQLite 保存重读及导出（SC-008、009）。
- [x] T019 [US5] 浏览器布局与共享核对回归、TypeScript/构建、Overview 增量和精确文件提交；回写 Issue，远程链接未验证时不关闭（SC-007、010）。

本轮证据与独立提交范围验证见 quickstart.md。远程 Spec 待推送验证、已有上传提取夹具失败不计作通过，均在该处明确记录；不关闭 Issue。

## 已认可统一 Demo 的实施（US6～US9）

- [x] T020 [US6、US7] 完整保留最新授权，更新 Issue、Spec/Plan/Research/模型/契约与验收映射，备份共享工作区。
- [x] T021 [US6、US7] 实现通用紧凑行、自动宽度控件、参数/条件扩展独立行，保留定义与证据。
- [x] T022 [US8] 实现热力学稳定性新建入口、分依据 case、前后端校验与隔离存储导出验证。
- [x] T023 [US9] 材料状态三元标题，三入口同一格式并验证实时和折叠显示。
- [x] T024 [US8] 实现前端按模块分类谱摘要、鉴权独立详情路由与图像/候选/质量/逐点/导出，跳转前保存与错误阻断。
- [x] T025 [US9] 手改“保存并完成”、明确禁用原因，复用真实保存链并保持原审核 gate。
- [x] T026 定向前后端测试、浏览器交互与三入口验证、独立候选构建，记录外部谱依赖与既有失败。
- [x] T027 使用 Overview Skill 回写已实现事实、精确提交、回写 Issue 验证；未推送远程链接不关闭。

T024 的完成范围是消费 #137 正式合同的前端路径；真实谱生成、后端鉴权/采纳及迁移验收仍归 #137，当前未据此关闭 #94。T026 的旧夹具失败、候选验证与部署边界见 quickstart。

## US10：模块默认折叠

- [x] T028 更新用户原话、Issue、Spec/Plan/Research/契约及验收映射。
- [x] T029 共享模块折叠组件覆盖四模块及仅谱模块；保留草稿、工具栏与只读行为，更新定向交互测试。
- [x] T030 三入口浏览器与相关表单回归、构建、Overview 回写及精确提交，回写 Issue 证据。

## US11：取消模块上下移动

- [x] T031 核查 #90/#94 历史，追加完整原话与 IMG-006，更新当前 Spec/Plan/Research/契约及 Issue #94。
- [x] T032 删除上下移动控件与闲置逻辑，保留顺序/折叠/删除合同并更新相关行为回归。
- [x] T033 验证共享表单、构建及三入口浏览器，回写 Overview/验收/Issue 并精确提交。

## US12：材料信息两行布局 Demo

- [x] T034 核查 #32/#50/#84/#90 历史，完整追加新原话、两次澄清及 IMG-007，区分来源与物理状态、结构与声子核处理。
- [x] T035 制作七字段首行、条件核处理第二行的独立 Demo，验证菜单、显隐、输入恢复、摘要及窄屏/暗色。
- [x] T036 留存演示及验证，更新 Issue #94 的待评审设计并按明确文件提交；不修改正式表单或业务数据。

## US13：结构家族第三行固定高度

- [x] T037 保留最新原话，核查 #109 高度条款的冲突，明确 mixed 退役替代旧兼容决定，更新 US12/US13 设计。
- [x] T038 制作三行 Demo，固定框高与横向轨道，验证空值/多项/长标签、删除、窄屏及类型显隐。
- [x] T039 留存演示/验证，串行同步 #94 和 #109 交叉说明并精确提交；不修改正式业务代码或执行数据清理。

## US12/US13 正式实施

- [x] T040 实现三行材料基本区和固定高度结构家族，保留已有字段、来源锚点、多选与键盘。
- [x] T041 从类型枚举、提取、建议、前后端读写和数据库约束退役 mixed，不兼容回填；保存当前只读审计证据。
- [x] T042 按已确认单份规范几何规则补齐核处理数据模型/契约/迁移，实施持久化、同值比较、返修、导出及结构关联。
- [x] T043 定向前后端、Go、浏览器与隔离候选验证；准备目标迁移，更新 Overview/验收/Issue 并精确提交。

- [x] T044 取得本机业务 schema 变更授权后，停止写入、重新备份与审计，应用 20261015_0094，核验实际 API 并恢复服务；不把隔离库结果替代本项。

## US14：费米能级 DOS 简化

- [x] T045 追加完整原话、两张原图及 FR-047～048 / SC-036，核对已有 #94 需求与组件责任。
- [x] T046 复用现有记录表单，跳过 DOS 重复折叠与定义选择，隐藏行下证据摘要，保留数据和记录操作。
- [x] T047 验证 DOS 编辑/复制/删除/只读及共享表单，完成构建、Overview 增量与独立提交。

## US15：每状态唯一 DOS（设计评审，未授权实施）

- [x] T048 逐字追加新原话，审计原任务历史备份与复制路径，留存 IMG-010，区分已核实事实与拟议归并策略。
- [x] T049 制作并验证相同副本/冲突/空值/不同压强/只读/来源的独立 Demo，保存 Issue 追加草案。
- [x] T050 展示完整草案与侧栏 Demo 后，取得“认可开始落地”的实际答复；已将完整原话和实施验收追加到 GitHub #94，读回确认原正文、type:feature 与 OPEN 均保留。
- [x] T051 用户“认可开始落地”后实现 DOS 唯一当前值、完整来源归档及原文侧栏；草稿/正式保存约束、共享表单、隔离 SQLite、浏览器和独立候选验证通过。证据见 dos-conflict-sidebar-demo.md 与 quickstart.md 的 US15 实施记录；不执行历史批量改写或业务迁移。

## US16：超导参数分行 Demo

- [x] T052 核对 #94 单行历史与 #139 Methods 边界，完整保存三点原话、普通补充字段澄清和 IMG-011，制作四个记录示例的独立 Demo。（FR-053～055）
- [x] T053 浏览器验证两行及按钮归属、Tc／μ* 单值与范围、不同近似、新增删除、扩宽回缩、复制、只读和保存重开；保存测量及截图，按明确文件提交，不写业务草稿。（SC-040～041；验证见 assets/tc-two-row-validation.json）
- [ ] T054 展示 Demo 并取得用户实际认可；再逐份展示 #94／#139 追加草案、确认和同步，不能用本轮制作授权代替 Demo 或 Issue 正文确认。（SC-042）
- [ ] T055 Demo 确认后同步 Research／契约，实施共享表单、验证三入口和持久化回归；原任务 Methods 补全由 #139 执行，完成后才回写正式行为 Overview。本轮不执行。（FR-053～055；SC-042）

## US17：复制按钮取舍与同行删除 Demo

调查和演示已完成，Demo 设计及 Issue 追加正文已获确认并同步；用户明确暂不落地，以下完成项不代表正式功能实现。

- [x] T056 [US17] 核查 GitHub #94、#90 合同与复制/删除代码，向 `docs/specs/94-property-record-editor/spec.md` 追加完整原话及待评审需求，留存 IMG-012 与独立图片索引。
- [x] T057 [US17] 制作 `docs/specs/94-property-record-editor/assets/record-actions-demo.html`，提供现有/建议切换、同行删除及窄容器演示，覆盖 FR-056～059。
- [x] T058 [US17] 用真实浏览器验证 SC-043～044，留存截图和 `docs/specs/94-property-record-editor/assets/record-actions-demo-validation.json`，在 `quickstart.md` 记录边界，准备完整 Issue 追加草案。
- [x] T059 [US17] 展示 `docs/specs/94-property-record-editor/assets/record-actions-issue-draft.md` 全文及 Demo，取得“认可设计并同步 #94，暂不落地”的实际答复后更新 Issue #94；读回核验原正文、完整获批草案、唯一类型与 OPEN 均保留（SC-045）。正式实施未授权，不建立生产路径实施任务。

顺序：T056 → T057 → T058 → 用户评审 → T059，已完成 Demo 及确认同步。正式四模块集成和业务保存均未实施；等待未来明确的落地指令，不自动推进。

## US16 修订：多方法与任意组数 Demo

- [x] T060 保存最新三点原话和 IMG-013／014，更新分行 Demo 为普通 Tc 标题、行首方法下拉和可增删的多组配对；新增字段改为添加空白方法行。（FR-060～062）
- [x] T061 浏览器验证三组配对、第二方法独立编辑／保存重开、删除中间组不串值、删除方法、至少一组／一行保护、只读及390px局部滚动，保存新版截图与验证记录。此项仅为 Demo 验证。（SC-046～047）
- [ ] T062 用户评审新版 Demo 后，再确认正式多结果数据表示及现有范围转换、证据、条件适用范围、保存导出与版本兼容；按既定流程逐份确认 Issue 增量。未确认前不实施正式组件或修复业务草稿。（SC-048，关联 #139）

## US17 正式实施

最新指令“开始落地！”授权以下任务；仅执行本故事，US15/US16 的未完成项不随之推进。

- [x] T063 [US17] 在 `frontend/src/components/PropertyRecordRow.tsx` 建立共享同行操作布局，接入 `SchemaDrivenRecordForm.tsx`、`TcRecordFields.tsx`、`ThermodynamicStabilityFields.tsx` 的主行（FR-057～058、SC-049）。
- [x] T064 [US17] 删除 `frontend/src/components/PropertyModuleEditor.tsx` 与 `SchemaDrivenRecordForm.tsx` 的复制入口回调，保留数据深复制及新增/删除合同，更新 `tests/01_decentralized_uploading/property-record-editor.test.tsx` 行为回归（FR-056、SC-050）。
- [x] T065 [US17] 运行相关共享表单回归、隔离候选 TypeScript/生产构建，在浏览器验证真实组件的宽/窄布局、同行删除、只读及输入保留，留存 `assets/record-actions-implemented-validation.json` 与截图（SC-049～050）。
- [x] T066 [US17] 更新本目录验收与检查表、现有 `docs/overview/01_Decentralized_Uploading_of_Superconductivity_Data/data-structure-and-form-mapping.md`，按本次差异提交并同步 Issue #94；保留远程文档待验证，不推送或关闭。

依赖：T063 → T064 → T065 → T066。设计映射为 FR-056→T064；FR-057/058→T063；SC-049/050→T065，授权与文档收尾→T066。已有原文的 Demo 限制按最新实施授权解释，不改写旧记录。

## 结构优化选项文案修订

- [x] T067 按用户原话修订 FR-046，删除 `frontend/src/i18n/zh/enums.ts` 的“（简谐基准）”及英文对应括号；同步当前 Overview，验证两字典仅目标显示值变化和相关 33 项回归，追加 Issue #94 文案需求。内部 classical_static 与数据契约不变。

## US18：晶体结构简洁折叠 Demo

- [x] T068 核查 #103/#94、现行结构折叠组件与默认行为，完整留存原话、原图及待评审 Spec。（FR-066～068）
- [x] T069 制作独立 Demo，验证空态/详情/待核对/只读、键盘、选择保留及390px，保存截图和记录。（SC-053～054）
- [x] T070 展示完整 Issue 追加草案和 Demo，获得用户实际答复后追加 #94；未获明确认可前不修改正式结构组件、API、数据库或 Overview。（SC-055）


## US18 正式实施

用户答复“认可。开始”确认完整 Demo 和追加草案，正式任务范围仅本故事。

- [x] T071 实现默认收起的轻量标题、详情归入展开体、当前结构来源入口及只读权限；同步论文只读详情。（FR-066～068）
- [x] T072 运行定向回归与隔离源码构建，真实浏览器核验 3Dmol 首次展开、视角/选择保留、来源、只读、键盘和390px，留存证据。（SC-053～055）
- [x] T073 同步 #94 的已认可增量与验收，更新 Overview 和 #103 后续覆盖说明，精确提交；不推送、不关闭 #94。
