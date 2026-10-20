# 实施任务：提升上传解析的 LLM 提炼质量

**输入**：[Spec](spec.md)。Issue 状态由 [#120](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/120) 管理。

## 阶段 1：程序归一化与核对口径（US1）

- [x] T001 `backend/db_helpers.py`：`parse_formula_composition` 支持括号分组与 Unicode 下标，拒绝不配对/空括号。（FR-001）
- [x] T002 `backend/ingest/upload_jobs.py`：`_formula_from_material` 只取唯一完整化学式；无法确定时原文保留为材料名，替代式元素数按组分统计。（FR-002）
- [x] T003 `backend/ingest/scientific_evidence.py`：与符号查表一致的空间群编号、晶系改为派生核对项。（FR-003）
- [x] T004 `backend/ingest/property_evidence.py`：核对来源排除参考文献、单批 120000 字符、每批 20 项；聚合只采用有定位证据的判断。（FR-004）

## 阶段 2：LLM 提取与提示词（US2）

- [x] T005 `backend/ingest/upload_jobs.py`：提取窗口合并至 12000 字符，页码取窗口起点。（FR-005）
- [x] T006 三处提示词补充解析乱码修正、材料命名、状态合并、等价表示与概括口径；分段缓存版本升为 9。（FR-006）
- [x] T007 `backend/rag/llm.py`：流式中途断开可重试，默认重试 2 次并退避。（FR-007）

## 阶段 3：验证

- [x] T008 新增 `tests/01_decentralized_uploading/test_issue120_extraction_quality.py`，更新 `tests/test_db_helpers.py`、`test_property_evidence.py` 中过时断言。
- [ ] T009 用户逐篇指定论文，基线（HEAD `913ec1c`）与新代码同模型对比，逐篇记录到 [验证记录](validation.md)；不等待整套样本齐全。（SC-001、SC-002）

## 阶段 4：二轮改进（FR-008、FR-009，2026-10-08 澄清后新增）

- [x] T011 `backend/ingest/scientific_evidence.py`：新增 `SYNTHESIS_FIELDS`，`field_records` 为概括/分类字段标注 `check_mode=synthesis`。（FR-008）
- [x] T012 `backend/ingest/property_evidence.py`：`checked_result` 支持引句回退（模型引句全部定位失败时回退提取阶段已验证证据）与 synthesis 分支（不因定位失败改判、理由不带定位错误）；`aggregate_candidates` 对 synthesis 字段忽略"本批未提及"的 missing；核对提示词要求 quote 原样复制；规则版本升为 `scientific-evidence-v6`。（FR-008、FR-009）
- [x] T013 补充 4 项单测（synthesis 标注与保留判断、事实字段引句回退、无证据仍判 missing、聚合忽略未提及批次）；定向回归与基线对比无新增失败。
- [x] T014 H3S 复验：同任务重跑字段核对，必填标红 5 → 1，剩余 1 项为模型判 unsupported 的有效标红（μ* 只填下界 0.1，原文为 0.1–0.13），无无效标红。
- [x] T010 Overview 回写已落地行为：`pdf-parsing-pipeline.md`（提取窗口、缓存版本 9、核对分批、synthesis 字段分级与引句回退、化学式归一化）与 `upload-llm-workflow-and-agent-analysis.md`（新增 2026-10-08 已实现补充章节、更正过期数字）。

## 阶段 5：材料家族全文判断（US3，2026-10-11 增量）

- [x] T015 [US3] 在 `tests/01_decentralized_uploading/test_issue120_material_family.py` 复现 H3S 误建新类，并覆盖多家族、真正新类、依据不足、引用工作、目录失败、无效 ID 与草稿版本冲突。（FR-010～014、SC-004～005）
- [x] T016 [US3] 在 `backend/ingest/material_family_classification.py` 读取运行时目录、整篇本文来源并分类；定位引句、校验 ID/别名、去重及保留失败原因。（FR-010～013）
- [x] T017 [US3] 在 `backend/ingest/upload_jobs.py` 共用汇总后接入分类，保留其他字段与新旧解析路径；在 `backend/ingest/property_evidence.py` 和 `backend/api/rag.py` 绑定服务端判断与当前字段版本。（FR-010、FR-012～013）
- [x] T018 [US3] 对唯一 H3S 草稿留私有快照并在任务锁、版本核对下定向重算；现有分类与核对已正确，故无需覆盖保存值；前后差异和真实论文结果见 `docs/specs/120-upload-llm-extraction-quality/validation.md`。（FR-014、SC-004）
- [x] T019 [US3] 两链路与相关前后端回归通过后，用 `big-project-overview-maintainer` 更新上传 Overview，只暂存本任务变更并自动提交。（SC-005）

## 阶段 6：论文总结与侧栏理由（US4，2026-10-11 增量）

- [x] T020 [US4] 更新总结生成与回退提示词，增加编号、语言、摘要重复校验和一次定向重试；失败保留其他草稿字段。（FR-015～016）
- [x] T021 [US4] 将总结核对归为论文归纳，保存当前版本的 AI 核对理由；上传和审核侧栏显示该理由而非“原文直接记载”。（FR-017）
- [x] T022 [US4] 调整中英文表单标签，用实际模型输入和组件测试验证生成、侧栏缺证、修改后理由失效及失败路径。（FR-015～017、SC-006～007）
- [x] T023 [US4] 核实唯一 H3S 草稿、留私有快照，版本匹配且未人工改写时定向重算；并行写回后只恢复总结，对照摘要和本文原文，记录前后差异。（FR-018、SC-008）
- [x] T024 [US4] 校对 #109 侧栏 Spec，更新验收记录；功能验证后回写上传 Overview，并以独立暂存树核验本任务提交范围。（SC-006～008）

## 阶段 7：材料家族归类理由（US5，2026-10-11 增量）

- [ ] T025 [US5] 在 `tests/01_decentralized_uploading/test_issue120_material_family.py`、`test_property_evidence.py` 和 `evidence-workflow.test.tsx` 复现 H3S 有具体核对 `reason`、缺 `ai_reason` 却显示直接记载的故障；覆盖失效、缺证和正式转接。（FR-019～021、SC-009～010）
- [x] T026 [US5] 复用 `backend/ingest/material_family_classification.py` 的归类理由，在 `backend/ingest/property_evidence.py` 按 #109 共用契约绑定当前分类与来源版本，禁止空泛理由自动支持。（FR-019～020）
- [x] T027 [US5] 在 `frontend/src/components/EvidenceWorkflow.tsx` 和中英文字典中显示当前模型判断逻辑；用真实 H3S 草稿核对材料家族 ID、引句及侧栏，不覆盖其他输入。（FR-020～021、SC-009）
- [ ] T028 [US5] 验证上传、刷新、正式来源与管理员重读；补齐 `data-model.md`、`contracts/material-family-reason.md` 和验收记录，再按 Overview 与 Issue 流程收尾。（SC-010）

## 2026-10-20 状态与核对修订

本轮已确认需求、原话、设计和实施任务见 [状态核处理提取与分支保留](state-review-convergence-20261020.md)。新规则覆盖该功能此前相冲突行为，历史原文与验收保留。

- [x] T036 本轮阶段1及验证证据见 [状态与核对修订](state-review-convergence-20261020.md)。
- [x] T037 本轮阶段2及验证证据见 [状态与核对修订](state-review-convergence-20261020.md)。
- [x] T038 本轮阶段3及验证证据见 [状态与核对修订](state-review-convergence-20261020.md)。
- [x] T039 本轮阶段4及验证证据见 [状态与核对修订](state-review-convergence-20261020.md)。
