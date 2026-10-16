# 实施任务

Issue 为协作状态唯一来源。本文件记录技术拆解。

## 基础与 US1

- [x] T001 [US1] 在 `tests/01_decentralized_uploading/scientific-evidence-markers.test.tsx` 和证据工作流测试新增全字段、空态、解决后入口及顶部列表移除的失败用例。
- [x] T002 [US2] 在 `tests/01_decentralized_uploading/test_field_suggestions.py` 新增字段目录、依据分类、生成/复核、采用与门禁失败用例。
- [x] T003 [US2] 扩展 `backend/ingest/scientific_evidence.py`、`evidence_proposals.py`、`property_evidence.py` 的空字段、建议与采用版本契约。
- [x] T004 [US1] 更新 `frontend/src/components/EvidenceFieldMarkers.tsx`、`EvidenceWorkflow.tsx` 及两个编辑入口和共用字段组件，补齐字段点击与三类结果侧栏。

## US2 与 US3

- [x] T005 [US2] 接入 `backend/ingest/upload_jobs.py` 上传建议生成及 `backend/api/evidence.py` 全量审核任务目的，验证取消、进度和失败恢复。
- [x] T006 [US3] 更新 `goserver/handlers/paper_evidence.go` 和 `backend/rag/scientific_sources.py` 的永久归档及推测归因，补齐跨层批准验证。

## 验收与交付

- [x] T007 [US3] 在真实存储回滚/隔离夹具中验证上传转论文、批准重读、空项保留、推测门禁及来源失效；记录到 `quickstart.md`。
- [x] T008 [US1] 完成桌面/窄屏、三入口、键盘、滚动及多状态浏览器验证，执行相关前后端测试与构建。
- [x] T009 [US2] 执行受控真实模型生成与复核，单独记录服务配置可用性、输出及局限，不修改真实科学记录。
- [x] T010 更新对应 `docs/overview/` 与 `README.md`、复核需求覆盖、独立审查修复、仅提交本任务差量，回写并按验收关闭 Issue。

顺序：T001/T002 → T003 → T004/T005 → T006 → T007/T008/T009 → T010。共享文件串行处理；每个故事须具备实际存储或浏览器信号后才标记完成。

## 2026-10-09 追加阶段：可核验的支持结论（US4，未实施）

旧 T001—T010 的完成状态只对应原验收；下列任务用于 FR-010—014 / SC-006—008。

- [ ] T011 [US4] 在 `tests/01_decentralized_uploading/test_property_evidence.py` 和定向真实来源测试中复现概括字段无引句仍显示 `supported`、事实引句不相关及派生输入失效，先锁定来源资格与版本边界。
- [ ] T012 [US4] 更新 `backend/ingest/property_evidence.py`、`backend/ingest/scientific_evidence.py` 与必要的来源契约：统一当前值的支持资格、定位失败状态、派生输入和规则版本；保留旧结果只读历史，不批量改写论文。
- [ ] T013 [US4] 在 `tests/01_decentralized_uploading/evidence-workflow.test.tsx` 与 `field-evidence-browser.mjs` 增加首屏可见引句、无 AI 理由仍显示依据、无来源提示及三入口鼠标/键盘用例。
- [ ] T014 [US4] 更新 `frontend/src/components/EvidenceWorkflow.tsx`、`EvidenceRegion.tsx` 及中英文字典：区分原文、人工记录和 AI 理由，首屏显示第一条来源，图片加载失败仍保留引句；侧栏不重复主表单值。
- [ ] T015 [US4] 按 `quickstart.md` 的新增验证路径，使用真实持久化和可复现 H3S 来源夹具核对上传→待审→批准重读、同名跨文件引句、概括多论断、旧版本和无来源状态；记录通过信号与未满足项。
- [ ] T016 [US4] 完成需求收敛和文档影响检查；使用 `big-project-overview-maintainer` 回写已实现行为，更新 `README.md` 的查看方法，并在 SC-006—008 全部满足后按 Issue 管理流程收尾 #109。

执行顺序：T011 → T012，T013 → T014，随后 T015 → T016；后端与前端实现可分别推进，但共同验收和 Issue 收尾必须串行。

## 2026-10-09 追加阶段：人类可读的侧栏与人工证据（US5，未实施）

以下任务对应 FR-015—021 / SC-009—012；旧任务的勾选不能证明本阶段完成。

- [ ] T017 [US5] 在 `tests/01_decentralized_uploading/evidence-workflow.test.tsx`、`scientific-evidence-markers.test.tsx` 和浏览器夹具中先复现作者 JSON、原文折叠、图像证据不可见及重复主表单内容的问题，锁定桌面/窄屏/键盘验收。
- [ ] T018 [US5] 在 `tests/01_decentralized_uploading/test_scientific_evidence_mysql.py` 与新增人工证据用例中先覆盖修改识别、有/无证据时的理由门禁、值版本失效、文件权限、回滚与任务清理。
- [ ] T019 [US5] 为 `backend/models.py` 和 Alembic 新增 `scientific_manual_evidence` 迁移与私有文件存储；在 `backend/api/evidence.py` 实现文字/截图/TXT/MD 的保存、鉴权预览、类型与哈希校验及待提交删除。
- [ ] T020 [US5] 在 `backend/api/rag.py`、`backend/services/paper_revisions.py` 和 `goserver/handlers/paper_evidence.go` 实现上传、返修及批准时的人工证据版本绑定与永久归档，验证失败恢复及不混入 `paper_files` 原论文语料。
- [ ] T021 [US5] 更新 `frontend/src/components/EvidenceWorkflow.tsx`、`EvidenceRegion.tsx` 与中英文字典：移除“当前内容”JSON 和第二套字段编辑器，系统原文默认展开并可折叠，人工修改区显示可读差异、理由和证据，末区名为“AI 理由”。
- [ ] T022 [US5] 更新 `backend/ingest/property_evidence.py` 与审核 AI 输入适配：人工文字和图片带 `human_provided` 来源独立输入，记录是否实际读取；模型无图像能力或读取失败时不假称已核验，并加入提示注入隔离测试。
- [ ] T023 [US5] 在上传、返修和管理员正式提交门禁中按服务端规范值逐字段检查人工修改理由及无证据原因；保留自动保存半成品、改回原值豁免与按字段定位的错误反馈。
- [ ] T024 [US5] 使用真实 MySQL 回滚事务、私有文件存储、审核 AI 图像路径和实际浏览器验证 SC-009—012，包括刷新、越权、重复提交、历史版本、图像失败及移动端，记录到 `quickstart.md`。
- [ ] T025 [US5] 复核 FR/SC/任务覆盖与文档影响；实际实现并验收后使用 `big-project-overview-maintainer` 更新 Overview、补充 `README.md`，再按 Issue 管理流程关闭 #109。

2026-10-09 实施记录：T011—T023 的主要代码路径及定向测试已写入；Overview 与 README 已同步可由代码及隔离测试证实的行为。无头 Chrome 的三入口隔离夹具已通过；真实业务 MySQL 的完整上传→返修→批准事务、真实 H3S 来源页面及可处理图片模型仍待验收，因此相关任务复选框和 T024—T025 均不提前标为完成。验证结果与环境限制见 [quickstart.md](quickstart.md)。

顺序：T017/T018 → T019/T023 → T020/T021/T022 → T024 → T025；T011—T016 的来源资格与首屏证据约束须在最终验收前完成。共享保存与审核边界串行处理。

## 2026-10-10 用户更正：自动填写与理由展示

- [x] T026 [US2] 更新 Spec、Research、Plan 与接口契约，明确推断/推测直接填主表单，侧栏不复制字段值。
- [x] T027 [US2] 上传生成后校验并补入空值，重建内容版本并保存 `adopted_basis`、`ai_reason` 和可定位来源；覆盖值变化失效及上传待审门禁的定向测试。
- [x] T028 [US1/US5] 侧栏改名“AI 理由”，移除重复的材料关系等字段编辑器，验证人工确认不会暗中采用不可见候选。
- [ ] T029 [US2/US3] 复核跨语言永久归档、实际上传→待审→批准及真实模型输出；按验证结果更新总览、README 和 Issue 验收记录。

## 2026-10-10 PDF 来源与局部预览（US6）

- [x] T030 [US6] 锁定 H3S 标题末页误引、旧页码缺失、整页低分辨率和待审历史误引；用独立 PDF 夹具覆盖错误页码、双栏、跨页、图表和权限。
- [x] T031 [US6] 首页标题与作者及普通 PDF 引句经当前文件哈希、文本层和字段身份核验；新结果保存与提交读取统一使用修正后的当前来源。
- [x] T032 [US6] 以 300 DPI 渲染引句上下各三行局部图和可信图表说明，超大区域分片，扫描件低分辨率显式提示；侧栏原始尺寸滚动、点击放大缩回。
- [x] T033 [US6] 待审旧标题来源 dry-run、备份、事务清理与重复运行测试；本机当前 H3S 一条任务已备份修正，已批准论文跳过。
- [ ] T034 [US6] 完成实际 H3S 登录页面的首页标题、作者及保留字段局部图与三角色桌面/窄屏复核；同步 Overview、README、#109 的验证边界，不替其他未验收项关闭 Issue。原材料关系局部图范围由 #127 废止。

## 2026-10-11 人工证据二选一（US7）

- [x] T035 [US7] 在 `tests/01_decentralized_uploading/test_issue109_manual_evidence.py` 和 `manual-evidence-section.test.tsx` 增加二选一门禁、图片/TXT/MD/PDF、历史只读、越权及刷新恢复的行为用例。
- [x] T036 [US7] 更新 `frontend/src/components/ManualEvidenceSection.tsx` 和中英文字典，当前编辑区只显示判断理由及互斥选项；上传路径不再要求手填来源说明，缺证路径只显示缺证理由。
- [x] T037 [US7] 更新 `backend/ingest/manual_evidence.py` 与 `backend/api/evidence.py`，验证 PDF 实际内容并保存私有附件，支持鉴权预览和有界文字提取，旧直接文字保持只读兼容。
- [ ] T038 [US7] 在 `backend/ingest/property_evidence.py` 的审核完成边界登记人工 PDF 实际读取状态，并验证提交/返修/批准沿当前字段版本按附件或缺证理由校验。
- [ ] T039 [US7] 运行定向前后端测试、构建和三入口浏览器流程，记录通过与限制到 `quickstart.md`；用 `big-project-overview-maintainer` 同步已实现行为及 README，不提前关闭仍有其他待验收项的 #109。

执行顺序：T035 → T036/T037 → T038 → T039；FR-025—028、SC-016—019 均映射到上述任务。

2026-10-11 进度：T035—T037 的真实组件与 FastAPI 私有文件路径已通过定向测试，Safari 上传页现场可见二选一及两条互斥控件。T038 的 PDF 审核输入和已读标记已通过服务端模拟模型测试，但尚无可搜索 PDF 的真实审核模型正向验收；T039 的管理员/超级管理员实页与完整上传→返修→批准链路也未验证，故保持未勾选。详见 [验证记录](quickstart.md)。

## 2026-10-11 保存反馈与同排对齐（US8/US9）

本阶段源于用户两张截图；2026-10-11 仅完成调查与记录，2026-10-12 已完成 US9 布局修复，具体证据见 T043—T044、T052—T053。

- [ ] T040 [US8] 用真实编辑器与工作流组合复现：结构家族修改后立即保存、自动保存后再存、自由输入未确认、版本缺失与冲突、成功但不关闭；核对请求和刷新重读，禁止仅 Mock 掉主表单保存边界。
- [ ] T041 [US8] 在 `EvidenceWorkflow.tsx`、`ManualEvidenceSection.tsx` 和上传/管理员调用处串联当前字段保存、刷新版本、说明保存及成功关闭；保留理由输入、滚动与焦点，处理未上传文件、部分失败、重复点击和跨会话响应。
- [ ] T042 [US8] 在人工说明 API 集成测试与工作流测试中覆盖真实字段/说明重读、409、主表单失败、说明失败、清空、多选、切换目标、重试与旧值说明失效；确认保存不提交、不批准且不伪造来源资格。
- [x] T043 [US9] 用真实 `MaterialStatesEditor` 与 `EvidenceFieldMarkers` 组合锁定 Autocomplete 标签归属及重复按钮，建立空值、单行、多选换行与相邻字段的浏览器尺寸基线。
- [x] T044 [US9] 修复组合控件来源标签复用与重复入口，统一结构家族浮动标签、辅助说明、字号字重及框体规则；保留多选、自由输入、删除、清空和键盘交互。
- [ ] T045 [US8/US9] 按新增 quickstart 在隔离草稿执行真实持久化及桌面/窄屏、中英文、上传/管理员/超级管理员验收；记录 SC-020—023 的测量、请求、结果与未满足项。
- [ ] T046 [US8/US9] 验收后使用总览维护 Skill 更新上传与审核 Overview、README 操作说明，回写 #109 本轮验收；既有未完成项全部满足前不得关闭 Issue。

保存路径：T040 → T041 → T042 → T045 → T046；布局路径可独立执行 T043 → T044 → T052 → T053。FR-029—033 与 SC-020—023 的覆盖见 [计划追踪表](plan.md)。

## 2026-10-11 模型归纳字段 AI 理由（US10）

- [ ] T047 [US10] 在 `tests/01_decentralized_uploading/test_property_evidence.py` 和 `evidence-workflow.test.tsx` 复现 H3S 材料家族 `supported` 且 `ai_reason` 为空时错误显示“原文直接记载”；覆盖其他归纳字段、直接原文、作者关键词、派生值及旧版本。（FR-034—037、SC-024—026）
- [x] T048 [US10] 在 `backend/ingest/property_evidence.py` 统一归纳字段的具体模型理由、当前版本来源类型和缺理由处理；核对提示词传入来源类别并要求依据到结论的简短解释。（FR-034—035）
- [x] T049 [US10] 在 `frontend/src/components/EvidenceWorkflow.tsx` 与中英文字典中按实际来源显示 AI 理由，旧结果具体理由可读，缺理由和失效时提示重核，不再误用直接记载兜底。（FR-035—036）
- [ ] T050 [US10] 在当前 H3S 草稿及上传、返修、管理员路径重读材料家族和其他归纳字段；验证内容/来源版本、正式转接与审核归因，记录真实通过与未覆盖项。（FR-037、SC-024—026）
- [ ] T051 [US10] 协调 #120、#128、#129、#66 的字段契约与验收，使用总览维护 Skill 回写已实现事实；仅暂存本任务差异并按仓库规则提交。（SC-025—026）

## 2026-10-12 结构家族布局验收与交付（US9）

- [x] T052 [US9] 使用 `frontend/test-fixtures/structure-family-layout.html` 的真实共用编辑器完成中英文、1440/390px、空值/单项/多项/长名称及重复核对更新的浏览器尺寸矩阵；验证自由输入新增、键盘删除、清空和来源入口，并运行上传/管理端回归及生产构建。（FR-032—033 / SC-022）
- [x] T053 [US9] 回写 Spec、Plan、Research、quickstart、上传与审核 Overview、README 和 #109 的布局验收，保留 US8 保存及其他未验收项的真实状态。（SC-022）

证据：布局回归修复前失败、修复后通过；7 个前端测试文件共 130 项通过，TypeScript/Vite 构建通过；Chrome 16 种布局通过。真实论文、人工说明接口与正式批准未操作，T040—T042、T045—T046 及 SC-020—021/SC-023 不随本次布局修复勾选。


## 2026-10-16 US11：字段影响隔离（已实现并完成专项验证）

本节为技术拆解，不表示 Issue 的协作状态；本次实施结果与限制见[字段隔离验证](field-isolation-validation.md)。

- [x] T054 [US11] 在真实共享编辑器、核对工作流和标记组合中建立“仅改核处理，三个派生项误红”的失败复现，记录保存前后状态、问题计数及人工说明；不 Mock 掉影响计算。（FR-038/040 / SC-027）
- [x] T055 [US11] 审查全部论文、材料、物性与结构字段的值/依赖边界，按后端 `state_records`、`record_claim` 和来源规则形成依赖矩阵；覆盖元素数、对称性、单位换算和真实科学条件。（FR-039/043 / SC-028）
- [x] T056 [US11] 修改共享 `evidenceFields.ts`、`EvidenceWorkflow.tsx` 及必要事件通知，复用现有依赖与稳定身份，移除同状态所有 derived 失效规则，过滤同值/重复通知；仅清理真实受影响项。（FR-038—041 / SC-027—029）
- [x] T057 [US11] 定向回归原生/组件双通知、同值选择、失焦、排序/删除、多材料/多记录、保留既有真实问题及人工说明，并验证真实依赖变化仍失效。（FR-039—042 / SC-028—029）
- [x] T058 [US11] 在隔离持久化与浏览器中验证上传、返修、管理员及超级管理员入口，观察编辑瞬间、超过 5 秒自动保存、失败/重试/迟到响应；记录边框、标签、计数、侧栏、请求与版本。（FR-042—043 / SC-030）
- [x] T059 [US11] 验收后回写上传与审核 Overview、Issue 和 quickstart；核验原话、原图及链接真实性，按仓库规则仅提交本次差异，保留 #109 其他未完成项。（SC-031）

顺序：T054 → T055 → T056 → T057 → T058 → T059。本轮 T054—T058 已有失败复现、依赖矩阵、共享实现、专项回归及四入口浏览器/MySQL 回滚证据；T059 的实现与文档独立提交为 `ba96f8d`，#109 已追加并回读核验相同实现及验证记录。原话/原图校验通过，本增量远程 Spec/图片链接尚未推送，CHK038 保持未完成；不因此关闭 #109 其他待验收项。
