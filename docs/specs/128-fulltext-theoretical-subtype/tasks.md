# 实施任务：理论二级类型全文归纳

**输入**：[规格](spec.md)、[计划](plan.md)、[研究](research.md)、[数据模型](data-model.md)、[契约](contracts/classification.md)、[验收](quickstart.md)。
**状态说明**：T001–T007 保留既有完成记录；T006 的完成只代表其原有自动化、真实模型及隔离浏览器证据，不能证明正式提交与审核的完整持久化。T010 已补充实际登录页的只读验收；T009 继续追踪正式来源端到端缺口，#128 保持开放。

## 阶段 1：准备

- [x] T001 在 `docs/specs/128-fulltext-theoretical-subtype/spec.md` 建立 #128 双向链接，并以同目录的 `plan.md`、`research.md`、`data-model.md`、`contracts/classification.md`、`checklists/requirements.md` 定义需求和边界。

## 阶段 2：用户故事 US1——全文分类（P1，MVP）

**目标**：理论论文按全文主要贡献得到三类或空值。
**独立验收**：`tests/01_decentralized_uploading/test_fulltext_theoretical_subtype.py` 的三类、空值、附件及多批次用例和 [H3S 真实模型记录](quickstart.md)。

- [x] T002 [US1] 在 `backend/ingest/theoretical_subtype.py`、`backend/ingest/upload_jobs.py` 实现全文分类、超长来源全覆盖、失败留空与非理论论文跳过。

## 阶段 3：用户故事 US2——归纳来源（P1）

**目标**：服务端持有分析，侧栏展示可定位的归纳理由。
**独立验收**：Methods-only、人工改值、来源版本与前端侧栏测试。

- [x] T003 [US2] 在 `backend/api/rag.py`、`backend/ingest/scientific_evidence.py`、`backend/services/paper_revisions.py` 保存服务端分析并阻止客户端伪造当前支持资格。
- [x] T004 [US2] 在 `backend/ingest/property_evidence.py`、`backend/ingest/scientific_evidence.py`、`backend/rag/scientific_sources.py`、`frontend/src/components/EvidenceWorkflow.tsx`、`frontend/src/pages/AdminPaperEditPage.tsx` 接入定位引句、综合理由和正式来源归因。

## 阶段 4：用户故事 US3——当前 H3S 草稿（P1）

**目标**：只重判目标字段并保护人工编辑及其他核对。
**独立验收**：定向重跑前后值、来源身份和其他字段哈希比较。

- [x] T005 [US3] 在 `scripts/reclassify-theoretical-subtype.py`、`backend/ingest/theoretical_subtype.py` 对目标 H3S 草稿按任务与文件名定向重跑。

## 阶段 5：完善与既有验收

- [x] T006 在 `tests/01_decentralized_uploading/test_fulltext_theoretical_subtype.py`、`tests/01_decentralized_uploading/evidence-workflow.test.tsx`、`tests/01_decentralized_uploading/field-evidence-browser.mjs` 覆盖三类/空值、长文、定位、草稿保护、隔离转接、真实模型和隔离浏览器；证据界限见 `docs/specs/128-fulltext-theoretical-subtype/quickstart.md`。
- [x] T007 在 `docs/specs/23-paper-ingestion-classification/spec.md`、`docs/specs/109-field-evidence-and-ai-suggestions/spec.md`、`docs/specs/120-upload-llm-extraction-quality/spec.md`、`docs/specs/114-multimodal-pdf-upload-agent/spec.md`、`docs/overview/01_Decentralized_Uploading_of_Superconductivity_Data/pdf-parsing-pipeline.md`、`docs/overview/02_Decentralized_Maintenance_and_Verification/literature-and-record-review.md`、`README.md` 回写新口径并完成本地提交。

## 阶段 6：收敛

- [x] T008 根据本次文档复核，在 `docs/specs/128-fulltext-theoretical-subtype/` 补齐可执行场景、技术上下文、研究备选方案、状态契约、准确任务路径、复跑命令与需求质量检查；不逐字存档用户原话。
- [ ] T009 [US2] [部分验收] 在隔离数据库中通过 `tests/01_decentralized_uploading/test_fulltext_theoretical_subtype_mysql.py` 或等效端到端夹具，验证上传提交、正式来源持久化重读及审核后归因；将命令、数据回滚和结果写入 `docs/specs/128-fulltext-theoretical-subtype/quickstart.md`。原 T004/T006 的函数级转接测试不能代替此项。
- [x] T010 [US3] 在已登录的实际 H3S 校对页只读核验刷新后的当前值、侧栏理由和定位来源，并在 `docs/specs/128-fulltext-theoretical-subtype/quickstart.md` 记录角色、页面与结果；原 T006 的 API 截获浏览器夹具不能代替此项。

## 依赖与执行顺序

T001 → T002 → T003/T004 → T005；T006/T007 在主路径完成后验收和回写。T009 依赖正式来源转接，T010 依赖 H3S 草稿与 UI 已可读取。T003/T004 共享来源文件，应串行核对；T009 与 T010 使用不同测试边界，可独立执行。MVP 为 US1；US2 和 US3 分别按各自独立验收通过。未得到 T009 的正式来源端到端证据前，不以复选框总数关闭 #128。

## 需求覆盖

| 来源 | 任务 | 验收信号 |
|---|---|---|
| US1、FR-001、FR-002、FR-005、SC-001、SC-002 | T002、T006 | 三类/空值、来源组全覆盖和 H3S 真实判断 |
| US2、FR-003、FR-004、FR-007、SC-003 | T003、T004、T006、T009 | 服务端分析、侧栏、来源转接及正式路径重读 |
| US3、FR-006、SC-004 | T005、T006、T010 | 人工值保护、单字段过期及真实页面刷新 |

全部用户故事场景分别由以上行和 [quickstart.md](quickstart.md) 的验证矩阵覆盖；T009/T010 是尚待取得的端到端证据，不表示已实施功能失效。
