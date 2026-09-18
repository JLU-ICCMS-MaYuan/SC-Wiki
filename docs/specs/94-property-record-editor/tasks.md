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
