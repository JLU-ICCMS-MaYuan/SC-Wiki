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
