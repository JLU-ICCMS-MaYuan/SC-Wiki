# 实施任务：超导参数提取与共用计算条件

**输入**：[Spec](spec.md)、[Plan](plan.md)、[Research](research.md)、[数据模型](data-model.md)、[提取契约](contracts/extraction.md)、[验收步骤](quickstart.md)。

**当前边界**：下列均为后续技术任务，未实施、未勾选；需求已确认不代表业务验收通过。进入代码实施仍需明确实施授权；远程链接待验证，不自动推送。

## 阶段 1：准备

**目的**：冻结科学预期与故障边界，避免用模型自己的结果作为答案。

- [ ] T001 在 `tests/fixtures/issue139/expected-table.json` 保存经原 PDF 逐行核对的 8 行独立预期与 Methods 阶段清单，记录论文文件 hash、页码和当前提交；在 `docs/specs/139-table-parameters-shared-methods/validation.md` 留存修改前缺失基线，不提交整篇论文。（FR-001～004，SC-001～003）

## 阶段 2：基础能力

**目的**：建立双入口可复用的来源、范围与元数据校验。

- [ ] T002 在 `tests/01_decentralized_uploading/test_issue139_scientific_context.py` 先覆盖表头／跨页表注、完整来源窗口、伪造引句、阶段、作用域例外、附加元数据与幂等校验，加入无法定位和来源不完整的失败断言。（FR-001、FR-005～008、FR-011，SC-004）
- [ ] T003 在 `backend/ingest/scientific_context.py` 实现共享表格包、Methods 来源窗口账本、上下文版本与来源验证；复用 IR／有效 main 和 SI 来源，超预算分窗且不截断原始块，失败保留缺口。（FR-001、FR-005、FR-007～008、FR-010～011，SC-004）

## 阶段 3：US1——完整填写表格参数（P1，首个增量）

**目标**：所有表行的 λ、ωlog、Tc 和 μ* 保持正确对应，先解决截图缺数。

**独立验收**：8 个逻辑表行与独立预期一致；300 GPa 两种近似分开；150 GPa 两端配对正确；未配对 μ* 两端留空。

### 测试

- [ ] T004 [US1] 在 `tests/01_decentralized_uploading/test_issue139_table_parameters.py` 先覆盖 8 行、谐／非谐分组、μ* 反向显式配对与仅范围反例、ωlog 别名／包装对象／千位分隔／未知单位，复现兼容入口丢参数的边界。（FR-001～004、FR-011，SC-001～002、SC-004）

### 实施

- [ ] T005 [US1] 在 `backend/ingest/domain_extraction.py` 及 `backend/ingest/upload_jobs.py` 将完整表格包传给真实分段提取，完善表头、分组及表注提示词，保持每个事实的原始块证据与逐行覆盖，不能只提最高 Tc。（FR-001～002、FR-008，SC-001～002）
- [ ] T006 [US1] 在 `backend/ingest/scientific_contracts.py`、`backend/ingest/tc_parameters.py` 统一规范参数名和单位，保留原始表示／来源元数据，区分明确配对与未配对范围，保证重复归一化不丢元数据、不加重复扩展。（FR-002～004、FR-011，SC-001～002、SC-004）
- [ ] T007 [US1] 在 `backend/ingest/upload_contracts.py`、`backend/ingest/scientific_drafts.py`、`backend/ingest/legacy_scientific_assembly.py` 修正旧输入边界的逐结果参数传递，禁止把状态级参数无条件复制到不同方法记录；去重包含近似与来源语义。（FR-002、FR-004、FR-010，SC-001、SC-004）
- [ ] T008 [US1] 在 `tests/01_decentralized_uploading/issue139-parameters.test.tsx` 先验证 Tc–μ* 两端及未配对范围显示，再在 `frontend/src/lib/tcParameters.ts`、`frontend/src/components/TcRecordFields.tsx` 做必要绑定修正；保留已有布局及人工清空行为。（FR-002～004，SC-002、SC-004）

## 阶段 4：US2——理解 Methods 共用条件（P1）

**目标**：模型依据全文把共同设置关联到正确结果，区分阶段、近似与局部例外。

**独立验收**：同方法多压力的已确认共用参数填入；QE、VASP、SSCHA 参数不混用，例外不被覆盖，缺展宽保持空。

### 测试

- [ ] T009 [US2] 在 `tests/01_decentralized_uploading/test_issue139_scientific_context.py` 先增加多压力共享、同材料不同计算阶段、局部网格／截断能例外、引用工作排除、歧义与缺参数反例；模型响应用固定候选验证服务端边界。（FR-005～008、FR-011，SC-003～004）

### 实施

- [ ] T010 [US2] 在 `backend/ingest/scientific_context.py` 实现任务当前模型的全文设置理解、明确作用域与推断关系候选，返回可定位值证据／范围证据及简短解释；不从共同化学式推出全篇共用。（FR-005～008、FR-011，SC-003～004）
- [ ] T011 [US2] 在 `backend/ingest/upload_jobs.py` 及 `backend/ingest/property_evidence.py` 把关联候选接入最终直接 Claim 检查后的既有建议阶段，按允许叶子路径深合并补空，保留局部条件及人工值；推断维持 uncertain，不改 `validate_claim` 门。（FR-005～010，SC-003～005）
- [ ] T012 [US2] 在 `backend/ingest/scientific_context.py`、`backend/ingest/upload_jobs.py` 处理完整来源 hash、规则／模型／提示词缓存失效、取消、窗口失败一次重试及明确缺口；失败时保留已有直接记录与空值，不生成虚假成功。（FR-007、FR-010～011，SC-003～004）

## 阶段 5：US3——核对、填写与持久化（P1）

**目标**：用户可分别查看表行、表注和 Methods 依据，修改、保存与重开后不丢关联。

**独立验收**：联合来源正确核对，推断标签准确，真实保存／提交／返修及导出保留参数、阶段和来源；人工改值后旧依据失效。

### 测试

- [ ] T013 [US3] 在 `tests/01_decentralized_uploading/test_issue139_workflow.py` 先覆盖生产 Worker 的直接提取→最终 Claim→建议补空→草稿保存顺序、跨块核对、已有 payload 的叶子补空、人工值保护及推断不冒充原文；不得 Mock 掉该路径自身。（FR-008～010，SC-004～005）

### 实施与集成

- [ ] T014 [US3] 在 `backend/ingest/property_evidence.py`、`backend/ingest/evidence_proposals.py` 完善表格／Methods 联合来源核对及建议内容／来源 hash 绑定，来源未读或有冲突时不能 supported；保持现有权限与人工接受边界。（FR-007～010，SC-004～005）
- [ ] T015 [US3] 扩展 `tests/01_decentralized_uploading/issue139-parameters.test.tsx`，并在 `frontend/src/components/SchemaDrivenRecordForm.tsx`、`frontend/src/components/EvidenceWorkflow.tsx` 将来源关联显示到现有理由入口、阶段参数显示到现有扩展列表；不把元数据当作科学输入控件，不改布局。（FR-006、FR-008～010，SC-003～005）
- [ ] T016 [US3] 在 `backend/ingest/property_modules.py`、`backend/ingest/upload_contracts.py` 和 `backend/ingest/scientific_drafts.py` 补齐来源关联元数据的记录校验与往返保留，使用服务端指纹防止旧解释绑定新值；只在真实提交／导出回归发现遗漏时定向修对应现有服务及 `backend/api/material_state_export.py`。（FR-004、FR-008、FR-010，SC-005）
- [ ] T017 [US3] 在 `tests/01_decentralized_uploading/test_issue139_persistence.py` 使用显式隔离 MySQL 依次核验草稿保存重开、正式提交、返修、证据核对结果、导出、版本冲突及权限，保留新元数据并确认无重复；SQLite 或只检查 JSON 字符串不能代替。（FR-004、FR-008～010，SC-005）

## 最终阶段：真实验收与收尾

- [ ] T018 [US1] [US2] [US3] 用 La–Sc–H 原 PDF 和任务当前模型运行真实新任务，按 `docs/specs/139-table-parameters-shared-methods/quickstart.md` 对照独立 8 行预期及 Methods；在 `docs/specs/139-table-parameters-shared-methods/validation.md` 保存来源、提交、模型、差异、漏行／错挂／编造计数与调用成本，未通过项不能勾选。（FR-001～011，SC-001～005）
- [ ] T019 [US1] [US2] [US3] 依据 `docs/specs/139-table-parameters-shared-methods/quickstart.md` 用真实浏览器核验参数、阶段、理由、人工改值、保存重开和重复点击；在 `docs/specs/139-table-parameters-shared-methods/validation.md` 登记实际截图与结果，浏览器测试通过不能替代 MySQL 或真实模型证据。（FR-003～004、FR-006、FR-008～010，SC-002～005）
- [ ] T020 使用全局 Overview Skill 更新 `docs/overview/01_Decentralized_Uploading_of_Superconductivity_Data/pdf-parsing-pipeline.md` 与 `pdf-ingestion.md` 的已验收行为及限制，核对 `docs/specs/139-table-parameters-shared-methods/checklists/requirements.md`，用 Issue Skill 回写 #139 真实验收及 Documentation Impact；仅暂存本功能文件并按 AGENTS.md 提交，不自动推送。（FR-010，SC-001～005）
- [ ] T021 获得单独明确推送授权后核验 `docs/specs/139-table-parameters-shared-methods/spec.md` 和图片远程可访问，记录 URL、分支／提交、时间、身份及响应内容；再回写 Issue #139 双向链接。只有全部验收、文档和链接门满足才关闭 Issue，当前不执行。（SC-001～005，Issue 关闭条件）

## 依赖与执行顺序

- T001 → T002 → T003 → T004 → T005 → T006 → T007 → T008 → T009 → T010 → T011 → T012 → T013 → T014 → T015 → T016 → T017 → T018 → T019 → T020 → T021。
- US1 可在 T008 后独立验收表格参数；US2 依赖 US1 的稳定记录身份，T012 后验收共用范围；US3 在 T017 后完成持久化边界，再执行真实论文和浏览器联合验收。
- 表单单测可在后端结果契约稳定后独立准备，但本计划不标 `[P]`：多个任务触碰相同模块、范围和来源元数据，实施默认串行，未授权并行 agent。
- T021 需要独立推送授权，不是自动部署或推送任务。远程链接未验证不妨碍生成本地规划，但不得宣布整体文档门或 Issue 关闭门通过。

## 需求覆盖

| 来源 | 任务 | 验收信号 |
| --- | --- | --- |
| FR-001～004 / US1 | T001～T008、T017～T019 | 全行、分组、单位、配对、兼容及保存 |
| FR-005～007 / US2 | T002～T003、T009～T012、T018～T019 | 全文作用域、阶段、例外与歧义 |
| FR-008～009 / US3 | T002、T005、T010～T019 | 逐字段依据、联合核对、推断标签 |
| FR-010 / US3 | T003、T007、T011～T020 | 双入口、缓存、持久化、证据、文档 |
| FR-011 / 全部故事 | T002～T004、T006、T009～T012、T018 | 空值、未知单位和不编造 |
| SC-001～002 | T001、T004～T008、T018～T019 | 8 行与 150 GPa 数值和配对 |
| SC-003～004 | T002～T019 | 共用条件、反例矩阵及真实对照 |
| SC-005 | T008、T011、T013～T019 | Worker／浏览器／MySQL 一致 |

## MVP 与增量策略

1. 首个增量完成 US1，先交付可独立验证的表格参数与明确配对。
2. 第二增量交付 US2，保留每项设置的阶段及作用域，不以全篇复制补空。
3. 第三增量交付 US3，完成核对、保存、提交及返修边界。
4. 只有原 PDF、真实模型、MySQL 与浏览器的各项证据均满足时才认定功能完成；本文件是技术拆解，不复制 Issue 协作状态。
