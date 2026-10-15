# 实施任务：人工证据输入与编辑可靠性

**Issue**：[#138](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/138)。

**输入**：[spec.md](spec.md)、[plan.md](plan.md)、[research.md](research.md)、[data-model.md](data-model.md)、[交互与接口契约](contracts/manual-evidence.md)。

用户已追加“开始落地”授权实施；勾选仅表示对应技术任务已有验证，不替代平台 Issue 状态。每项实施前复查共享工作区和 #109 最新进展；同一文件修改串行执行。

## 阶段 1：准备

- [x] T001 在 `docs/specs/138-manual-evidence-input-reliability/research.md` 记录运行制品来源与“提供证据”异常的隔离浏览器时序，区分整页导航、组件重建和旧响应覆盖，并复核 #109 US8 实际进展及可复用保存逻辑。

## 阶段 2：基础能力

- [x] T002 对照 `frontend/src/components/EvidenceWorkflow.tsx`、`frontend/src/lib/evidenceFields.ts`、`backend/api/evidence.py` 和 `backend/ingest/manual_evidence.py`，在 `docs/specs/138-manual-evidence-input-reliability/contracts/manual-evidence.md` 核定稳定字段身份、当前值读取、保存回调及分阶段错误契约；不得增加第二套保存流程或绕过版本检查。

## 阶段 3：US1——编辑内容可靠保留（P1，MVP）

**目标**：多字段、侧栏重开、后台刷新及失败重试都保留正确输入。

**独立验收**：填写至少两个字段的不同理由及证据状态，交替切换、关闭重开、延迟/乱序返回与失败重试，核对内容及归属。

- [x] T003 [US1] 在 `tests/01_decentralized_uploading/manual-evidence-drafts.test.tsx` 与 `tests/01_decentralized_uploading/manual-evidence-section.test.tsx` 先覆盖旧读取覆盖新输入、切换选项、字段/任务隔离、侧栏重开、待上传 File 保留及部分成功等失败场景。
- [x] T004 [US1] 在 `frontend/src/lib/manualEvidenceDrafts.ts` 和 `frontend/src/components/EvidenceWorkflow.tsx` 建立编辑会话草稿及修订保护，复用已有保存协调能力；区分整份版本变化与字段值变化，旧响应不能重置新的草稿或关闭新侧栏。
- [x] T005 [US1] 在 `frontend/src/components/ManualEvidenceSection.tsx` 接入该草稿管理，区分加载/无修改/失败，保留选择、理由和文件，串联说明与文件的分阶段结果；成功后的关闭与焦点恢复遵循 #109，未上传文件不可被误报已保存或静默丢弃。

## 阶段 4：US2——修改后立即看到入口（P1）

**目标**：无需等待自动保存或刷新，就能查看当前修改的人工说明入口。

**独立验收**：书目、多选/自由输入、材料状态及物性字段分别验证立即打开和自动保存后打开；加载失败不误显示无修改。

- [x] T006 [US2] 在 `tests/01_decentralized_uploading/manual-evidence-editor.test.tsx` 先编写主编辑器与共享侧栏集成回归，覆盖五秒前打开、保存后版本刷新、主值保存失败、缺版本、改回原值及当前值变化后的旧说明保护。
- [x] T007 [US2] 在 `frontend/src/components/EvidenceWorkflow.tsx` 与 `frontend/src/components/ManualEvidenceSection.tsx` 根据稳定身份和当前值立即展示待同步入口；显式保存/上传时等待主值保存并取得相同字段当前版本，打开查看不调用模型或隐式提交。
- [x] T008 [US2] 在 `frontend/src/components/UploadTaskEditor.tsx` 与 `frontend/src/pages/AdminPaperEditPage.tsx` 接通共用保存/版本同步及草稿状态，覆盖上传、返修、管理员和超级管理员；Tc 校验等失败须保留输入并指明阶段，防止获焦后台回写覆盖正在编辑的人工说明。

## 阶段 5：US3——拖拽文件与粘贴截图（P2）

**目标**：点击、拖拽和截图粘贴共用人工附件流程。

**独立验收**：支持类型完成拖入/上传/预览/删除，真实截图粘贴无需本地文件；文本框粘贴不变，拖拽不导航。

- [x] T009 [US3] 在 `tests/01_decentralized_uploading/manual-evidence-section.test.tsx` 先覆盖点击/drop/paste 同一校验、剪贴板图片真实 MIME 与命名、空/无效/超限输入、满五项、默认行为阻止、普通文本粘贴和请求失败后文件保留。
- [x] T010 [US3] 在 `frontend/src/components/ManualEvidenceSection.tsx` 与 `frontend/src/i18n/zh/evidence.ts`、`frontend/src/i18n/en/evidence.ts` 实现可聚焦拖拽/粘贴区及一致文件处理、预览清理和提示；沿用 `backend/api/evidence.py` 的鉴权人工文件接口及 10 MiB/5 项约束。

## 阶段 6：跨故事验证与文档收尾

- [ ] T011 按 `docs/specs/138-manual-evidence-input-reliability/quickstart.md` 执行前端定向回归、生产构建、既有人工证据接口回归、隔离真实存储与 Chrome/Safari 浏览器矩阵；记录命令、版本、结果与失败，不以 Mock 覆盖代替实际导航和系统剪贴板证明。
- [ ] T012 实现验收后使用全局总览维护 Skill 更新 `docs/overview/01_Decentralized_Uploading_of_Superconductivity_Data/pdf-parsing-pipeline.md`、`docs/overview/02_Decentralized_Maintenance_and_Verification/literature-and-record-review.md` 与 `README.md`；回写 `docs/specs/138-manual-evidence-input-reliability/quickstart.md` 的证据及 #138 文档影响，按授权与实际结果处理远程链接和关闭门。

## 依赖与执行顺序

T001 → T002 → T003 → T004 → T005 → T006 → T007 → T008 → T009 → T010 → T011 → T012。

US1 是草稿保护基础，US2 复用该基础，US3 复用前两者的写入路径。共享文件较多，本方案不标记可直接并行的任务，也不要求并行代理。每个故事完成后可独立验收，浏览器证据最终共同收敛。

## 需求覆盖

| 来源 | 任务 | 说明 |
|---|---|---|
| FR-001 / US3 | T009—T010 | 类型矩阵、拖入与保留点击 |
| FR-002 / US3 | T009—T011 | 合成事件回归及真实系统截图粘贴 |
| FR-003 / US3 | T009—T011 | 三入口同一上传/校验/预览/删除 |
| FR-004 / US3 | T009—T011 | 拖拽默认导航与普通文本粘贴隔离 |
| FR-005 / US2 | T006—T008、T011 | 立即打开、保存后打开与真实交互 |
| FR-006 / US1 | T003—T005、T011 | 字段/任务/值修订、旧响应及侧栏重开 |
| FR-007 / US1、US3 | T001、T003—T005、T009—T011 | 导航根因证据、交互与组件状态保护 |
| FR-008 / US1、US2 | T002—T008、T011 | 主值/说明/文件保存顺序与冲突 |
| FR-009 / US1 | T003—T005、T011 | 保存重读、未上传保护及部分成功重试 |
| FR-010 / 全故事 | T002、T008、T010—T012 | 四入口、鉴权、历史和提交规则回归 |
| SC-001 | T009—T011 | 支持类型与截图完成完整附件流程 |
| SC-002 | T006—T008、T011 | 无需手动刷新即可补证 |
| SC-003 | T003—T005、T008、T011 | 多字段及后台响应不覆盖 |
| SC-004 | T003—T008、T011 | 失败保留、版本冲突与刷新读回 |
| SC-005 | T001、T008、T011—T012 | 真实浏览器、运行来源及共用入口证据 |

全部故事验收场景还应逐项对照 [quickstart.md](quickstart.md) 的矩阵，不因单项测试通过勾选整个故事。

## 实施证据与剩余项

T001—T002：Research 实施核对和既有接口契约；T003—T010：三份人工证据测试及共用生产路径，63 项定向回归、Chrome 四入口通过。未保存内容和新字段身份归并均有回归。

T011 保持未完成：Chrome、隔离 SQLite 与文件存储已验证，Safari 和真实 MySQL 完整业务链仍待验收。T012 的本地 Overview、README 与验证记录已更新；远程链接未发布，关闭门仍未满足。详见 quickstart.md。

## MVP 与增量策略

先完成 US1 输入保护；再交付 US2 即时入口与保存同步；最后增加 US3 拖拽和截图粘贴。任何阶段都不改来源支持资格或批准权限，不以文档生成作为任务完成。
