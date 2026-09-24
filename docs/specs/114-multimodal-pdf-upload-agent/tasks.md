# 实施任务：多模态 PDF 解析与证据驱动上传 Agent

**输入**：[spec.md](spec.md)、[plan.md](plan.md)、[research.md](research.md)、[data-model.md](data-model.md)、[contracts/](contracts/)

## 阶段 1：准备

- [ ] T001 [US1] 核对 Docling、MinerU 附加许可证、Python/镜像兼容性并固定 requirements.txt、docker/requirements.txt 版本。
- [ ] T002 [US1] 建立至少 50 篇论文的脱敏评测清单、标注格式和基线输出，保存到 tests/fixtures/issue114/README.md（不提交受限制论文文件）。
- [ ] T003 [P] [US5] 增加解析方案配置（`text`、`layout`、`ocr`、`vision`、`native_pdf_llm`）、能力探测和 Shadow/灰度/默认开关，保存到 backend/rag/config.py 与 backend/ingest/parser_rollout.py。

## 阶段 2：基础能力

- [x] T004 [P] [US1] 定义 backend/ingest/document_ir.py 的 Pydantic/TypedDict 模型、枚举、哈希和几何校验。
- [x] T005 [P] [US1] 定义 backend/ingest/document_parsers.py 的 DocumentParser、DocumentSource、ParserDecision、ParserRun、解析方案和统一错误；ParserRun 记录 `reading` 子状态。
- [x] T006 [P] [US2] 定义 backend/ingest/claim_evidence.py 的 Claim、EvidenceLocator、来源分类和定位校验器。
- [x] T007 [P] [US3] 定义 backend/ingest/coverage_audit.py 的 CoverageReport、表格行/结果段落/截断信号检查。
- [x] T008 [P] [US3] 为 T004–T007 先写契约测试 tests/01_decentralized_uploading/test_issue114_multimodal_pdf_agent.py。

## 阶段 3：用户故事 1——解析复杂论文（P1，MVP）

**独立验收**：数字、扫描、双栏、表格和公式样例按指定解析方案生成合法 Document IR；方案不可用时产生可观察失败、重试或人工状态，不自动切换方案。

- [x] T009 [US1] 实现 PyMuPDF 文本解析方案，补齐文本块、图片块、页边界、内容哈希和方案元数据；不可用时返回明确错误。
- [x] T010 [US1] 实现 DoclingParser 的可选导入、版本记录、块/表格/公式/图像映射和方案不可用错误。
- [x] T011 [US1] 实现 MinerUParser 的 tier 配置、版本记录、稳定 block ID 和方案不可用错误。
- [ ] T012 [US1] 实现 NativePdfLlmParser 适配器：接收供应商 PDF/页面输入，只输出合法 Document IR，不直接写库；Claim 候选由独立步骤生成。
- [ ] T013 [US1] 在 backend/ingest/upload_jobs.py 接入解析方案路由：PDF 进入选定方案，TXT/MD 保留直接读取，CIF/POSCAR 保留 ASE 结构候选和用户确认，旧 Markdown 缓存继续可读。
- [ ] T014 [US1] 增加数字 PDF、扫描页、复杂表格、公式、双栏和补充材料的真实/合成集成测试，覆盖不同解析方案选择和方案不可用时的显式失败。

## 阶段 4：用户故事 2——有证据的科学 Claim（P1）

**独立验收**：Claim 通过定位后才能转换为现有草稿；不能定位的结果显示不确定并保留原因。

- [ ] T015 [US2] 将 Document IR 块和表格单元接入现有分段/汇总提示输入，输出版本化 Claim。
- [ ] T016 [US2] 在 upload_jobs.py 中调用 Claim 定位校验并映射现有 field_path、basis_kind、source_kind 和 Evidence。
- [x] T017 [US2] 增加 Claim 无效、跨文件、错误页码、越界 bbox、OCR 来源和旧 quote 兼容定位测试。
- [x] T018 [US2] 建立 Alembic 文档块、解析运行和 `paper_evidence_locators` 定位关联迁移，并在 backend/models.py、goserver/models/models.go 中加入只读映射。
- [ ] T019 [US2] 在提交事务和 revision 服务中把文档定位复制到新的当前 revision，保持旧 revision 不作为完整文档打开，并补齐真实数据库回归。

## 阶段 5：用户故事 3——覆盖审计与安全停止（P1）

**独立验收**：覆盖不足、预算耗尽、解析器失败和 RQ 入口失败都不会形成假完成。

- [x] T020 [US3] 把 CoverageReport 和 `reading` 子状态接入上传任务 artifact manifest 与前端进度详情，不扩展既有五阶段主状态。
- [ ] T021 [US3] 实现 AgentToolRegistry、ActionBudget 和 read_page/read_region/extract_table/inspect_figure/search/validate/check_coverage 工具。
- [ ] T022 [US3] 接入有限 Agent 循环、取消、超时、重试和“需要人工”停止状态，不保存思维链。
- [ ] T023 [US3] 增加指定解析方案不可用、模型超时、GPU 缺失、输出截断、工具超限和 RQ 失败收敛集成测试，确认不会静默换方案。

## 阶段 6：用户故事 4——区域证据（P2）

**独立验收**：上传者和审核员可从字段进入页码、区域和引句；区域失败仍有文本证据。

- [ ] T024 [US4] 增加文档 Evidence API，返回文件、PDF/印刷页码、bbox、多边形、块关系、解析方案和 `paper_evidence_locators` 关联信息。
- [x] T025 [US4] 增加按原 PDF 页码和 bbox 的按需渲染接口，限制文件归属和页面范围。
- [x] T026 [US4] 修改 EvidenceWorkflow、UploadTaskEditor 和审核页面，显示区域证据、OCR 标记和渲染失败提示。
- [ ] T027 [US4] 增加桌面/窄屏/键盘、刷新恢复、旧 Evidence 和无区域数据前端测试。

## 阶段 7：用户故事 5——渐进上线（P2）

**独立验收**：Shadow/灰度/默认均可配置，质量门未通过不能默认，新链路失败可回退旧链路。

- [ ] T028 [US5] 实现 Shadow 结果存储、旧/新结果对照摘要和不影响用户草稿的任务分支。
- [ ] T029 [US5] 实现灰度比例/允许名单、任务级显式旧链路回退、解析方案选择和安全审计日志。
- [ ] T030 [US5] 建立 50 篇论文基准运行器和报告，计算 SC-001～SC-003 指标。
- [ ] T031 [US5] 增加默认切换质量门、配置拒绝、方案选择和回滚测试，不要求用户长期绑定单一解析器。

## 最终阶段：完善与跨故事事项

- [ ] T032 [P] 更新 docs/overview/01_Decentralized_Uploading_of_Superconductivity_Data/pdf-parsing-pipeline.md、data-structure-and-form-mapping.md 和 upload-llm-workflow-and-agent-analysis.md。
- [ ] T033 [P] 更新 README.md、部署依赖、模型资源和无 GPU 时的方案选择/失败处理说明。
- [ ] T034 运行 Python、前端、Go、迁移、RQ、浏览器和 50 篇基准验证，记录 docs/specs/114-multimodal-pdf-upload-agent/validation.md。
- [ ] T035 使用 big-project-overview-maintainer 回写已落地行为；只写已实现事实，不写未来设计。
- [ ] T036 核对 Issue/Spec 双向链接、Documentation Impact、git status/diff，按 AGENTS.md 只提交本 Feature 文件。

## 依赖与执行顺序

- T001–T008 阻断所有用户故事。
- T009–T014 完成后才可接入 Claim；T015–T019 完成后才可做正式提交。
- T020–T023 依赖 IR 和 Claim；T024–T027 依赖正式定位数据；T028–T031 依赖前述链路可运行。
- 同一文件上的任务串行；仅 T003/T004/T005/T006/T007/T008/T032/T033 可在依赖满足后并行。

## 需求覆盖

| 来源 | 任务 | 说明 |
| --- | --- | --- |
| FR-001～FR-004 / US1 | T004–T014 | 适配器、解析方案、媒体路由、IR、页面/块/表格/公式 |
| FR-005～FR-006 / US2 | T006、T015–T019 | Claim、Evidence、定位和正式保存 |
| FR-007～FR-010 / US3 | T007、T020–T023 | 覆盖、工具预算、方案不可用时的失败收敛和人工状态 |
| FR-011 / US5 | T003、T028–T031 | Shadow、灰度、默认和质量门 |
| FR-012 / US4 | T018、T019、T024–T027 | 文档块、定位关联表、当前 revision 和区域证据 |
| FR-013～FR-014 | T015、T019、T024、T032–T035 | 联网隔离、既有提交/审核/发布兼容 |
| SC-001～SC-008 | T014、T017、T019、T023、T027、T030、T031、T034 | 指标、回归、端到端和上线门禁 |

## MVP 与增量策略

1. MVP：T001–T019，完成可定位 IR、Claim、定位关联表和正式当前 revision 数据，旧链路仍为默认。
2. 第二阶段：T020–T027，加入覆盖审计、有限 Agent 和区域证据。
3. 第三阶段：T028–T031，完成基准、Shadow、灰度和默认门禁。
4. 收尾：T032–T036，完成文档、验证、Overview 和 Issue 关闭准备。


## 2026-09-24 阶段复核

T010/T011 已用真实 SDK 与本地 PDF 验证，详见 [验证记录](validation.md)。
T003 的配置选择尚无质量门和 Shadow 运行；T006/T007 的早期检查器尚不足以证明
严格 Claim 定位与漏记录检测；T013 的文本兼容桥虽已修复目录及缓存，仍需完整
上传任务和后续 Claim/覆盖门禁验证，因此撤回其先前完成标记。T001 的库安装已验证，
模型许可与 Docker 验收未完成；T002 尚无 50 篇人工标注评测集。


## 2026-09-24：证据、覆盖与区域查看收敛

- T006/T007/T017：严格校验文件、页码、解析器版本、来源类别、区域与引句；独立统计
  未读页、疑似结果块、未覆盖表格行和图像/公式。人工推断不自动标为 validated。
- T018：修复未部署的初版迁移；真实独立 MySQL 8.4 验证增量建表、升版、事务回滚、
  删除与降级。随后仅将该增量应用到本机数据库，三张定位表仍为空。
- T020/T025/T026：保持既有主阶段，展示 reading 子状态；校对抽屉按需请求区域 PNG，
  失败和旧来源保留页码/引句；上传时可选择已支持的解析方案。
- T015/T016/T019/T021/T022/T024 已有接入代码和定向验证，但完整领域契约、正式审核/
  返修/权限端到端与真实模型验收仍待完成，不据此全部勾选。
- T031 已拒绝缺失/失败报告的默认切换；T028/T029/T030 尚无完整 Shadow/基准验收。
  50 篇人工标注集尚未提供。详细证据见 [验证记录](validation.md)。

## 2026-09-24：离线评测与默认门收敛

- T002/T030：已建立人工标注、成对输出与独立验收契约，以及离线逐论文/逐类别评测
  CLI；输入摘要、失败分母、重复预测、条件关联和区域定位均可检查。真实 50 篇清单、
  完整上传运行驱动及输出导出仍未完成，不勾选完成。
- T031：默认门核对版本 1 详细报告，不再接受仅有汇总数字的早期报告；要求全部类别
  有样本、三个复杂类别分别提升。合成样本只用于评分与门禁测试，不算质量验收数据。
