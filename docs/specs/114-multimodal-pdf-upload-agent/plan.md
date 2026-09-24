# 实施计划：多模态 PDF 解析与证据驱动上传 Agent

**GitHub Issue**：[ #114](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/114)

**日期**：2026-09-23

**Spec**：[spec.md](spec.md)

## 摘要

在现有 RQ 上传 Worker 内增加解析方案选择层和统一 Document IR。Docling 负责默认结构化文本解析，MinerU、视觉方案和 PDF 原生多模态 LLM 按任务策略处理复杂页面或跨页理解，PyMuPDF 作为可选文本方案。指定方案不可用时明确失败、重试或转人工，不静默切换为另一种方案。Claim、Evidence 和 CoverageReport 在进入现有草稿/科学数据契约前由程序校验。正式提交时保存文档定位数据和定位关联表，前端按需从原 PDF 渲染区域。

## 技术上下文

- **语言与版本**：Python 3.12、FastAPI、RQ、SQLAlchemy/Alembic；React/TypeScript；Go 现有论文接口。
- **主要依赖**：现有 PyMuPDF、GROBID、Redis/RQ、MySQL、Qdrant；新增 Docling 和 MinerU；PDF 原生 LLM 通过现有模型配置适配器接入。
- **数据存储**：Redis 保存任务运行态；任务 artifact 保存临时 IR/Claim；MySQL 保存当前论文 revision 的正式文档块、定位关联表、Evidence 和论文 revision 关联；原 PDF 保持现有文件存储。
- **测试体系**：pytest、真实隔离 Redis/RQ、SQLite/MySQL 回归、Vitest、浏览器夹具、Go 测试和 50 篇论文基准。
- **目标平台**：本地 CPU、可选 GPU、Docker Worker；无 GPU 时必须可启动，指定视觉方案不可用时明确失败或转人工。
- **性能目标**：默认路径不因视觉模型阻塞；Agent 最多 12 次行动；单工具最多 2 次重试；任务失败必须在状态机中收敛。
- **约束**：科学数据不能由外部网络补全；解析器不直接写业务数据库；保留旧缓存和旧 Evidence 读取；不保存截图为唯一证据。
- **规模范围**：单任务一个正文和多个附件；正式论文按 revision 保存定位；首期不批量重解析历史论文。

## 质量门

| 约束来源 | 强制要求 | 设计如何满足 | 状态 |
| --- | --- | --- | --- |
| AGENTS.md | docs 使用简体中文；默认分支为 `mayuan`；变更后定向暂存和提交 | 全部产物使用中文；实施前后核对分支、状态和差异 | 通过 |
| Overview | Redis 是上传任务状态来源；正式提交/审核事务保留现有边界 | 解析层只产出 IR/Claim；上传状态和提交事务复用现有服务 | 通过 |
| FR-001～FR-006 | 解析器与 Claim 必须可定位且不可直接写库 | adapter → IR → Claim → validator → draft 的单向链路 | 通过 |
| FR-007 / SC-002 | 必须检查覆盖和区域定位 | CoverageReport、块/表格行清单和证据定位测试 | 通过 |
| FR-010 / SC-004 | 失败可见、可重试或人工处理 | 统一 ParserRun 状态、所选方案、错误原因和 RQ 失败收敛 | 通过 |
| FR-011 / SC-008 | Shadow、灰度、默认可配置 | rollout 配置、任务级方案选择和显式旧链路回退，不静默切换解析器 | 通过 |
| FR-012 | 正式定位数据支持 revision | 文档块、定位关联表、当前 revision 复制和删除回归 | 通过 |
| AGENTS.md Git | 修改后合理验证并自动提交，不能混入其他改动 | 本轮完成验证后按文件定向暂存并提交 | 实施中 |

## Feature 文档结构

```text
docs/specs/114-multimodal-pdf-upload-agent/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── tasks.md
├── analysis.md
├── contracts/
│   ├── parser.md
│   ├── document-ir.md
│   ├── claim-evidence.md
│   ├── agent-tools.md
│   └── rollout.md
└── checklists/requirements.md
```

## 源代码结构

```text
backend/ingest/
├── document_ir.py
├── document_parsers.py
├── claim_evidence.py
├── coverage_audit.py
├── parser_rollout.py
└── upload_jobs.py
backend/api/
├── upload_tasks.py
└── rag.py
backend/models.py
alembic/versions/20260923_0114_document_ir.py
frontend/src/components/
└── EvidenceWorkflow.tsx
frontend/src/lib/
└── documentEvidence.ts
requirements.txt
docker/requirements.txt
tests/01_decentralized_uploading/
└── test_issue114_multimodal_pdf_agent.py
```

**结构选择**：解析方案、IR、Claim 提取、Claim 校验和覆盖审计保持单一职责；`upload_jobs.py` 只负责编排和现有草稿转换。`DocumentParser` 只返回 IR，Claim 由独立提取步骤生成。正式定位数据归当前论文 revision 所有，通过 `paper_evidence_locators` 连接现有 `paper_evidences` 与 `paper_document_blocks`，不在前端复制科学事实。区域图片由原 PDF 和定位数据按需生成，不增加截图存储表。

## 需求到设计的映射

| 来源 | 设计组件/接口 | 验证方式 |
| --- | --- | --- |
| FR-001～FR-004 / US1 | `DocumentParser`、解析方案、`DocumentIR`、`DocumentBlock` | parser 契约、媒体路由、数字/扫描/表格样例 |
| FR-005～FR-006 / US2 | `Claim`、`EvidenceLocator`、`validate_claim` | 引句、页码、bbox、旧缓存定位测试 |
| FR-007 / US3 | `CoverageReport`、`audit_coverage` | 表格行、压力组合、截断信号测试 |
| FR-008 / US3 | `AgentToolRegistry`、`ActionBudget` | 工具白名单和预算测试 |
| FR-009 / FR-013 | `basis_kind`、`source_kind`、联网隔离契约 | 外部结果不能进入科学 Claim 测试 |
| FR-010 / US3 | `ParserRun`、解析方案选择、RQ 失败收敛 | 隔离 Redis/RQ 任务测试 |
| FR-011 / US5 | `RolloutConfig`、方案选择、shadow/gray/default 路由 | 配置、显式回退和质量门测试 |
| FR-012 / US4 | 文档定位 ORM、`paper_evidence_locators`、当前 revision 复制 | MySQL/SQLite 迁移和删除回归 |
| FR-014 / US2/US4 | 现有 `upload_jobs.py`、`scientific_evidence.py`、前端 Evidence 工作流 | 真实提交/审核回归 |

## 实施阶段

1. **Setup**：锁定依赖版本、许可证、配置和 50 篇评测集清单。
2. **Foundational**：建立 IR、解析器协议、解析方案选择、Claim、Evidence、Coverage 和 rollout 配置。
3. **US1**：接入 Docling、MinerU、PyMuPDF 文本方案和 PDF LLM IR 适配器，保持 TXT/MD 与 CIF/POSCAR 旧链路可用。
4. **US2**：接入 Claim 提取、证据校验、现有草稿转换和正式文档定位迁移。
5. **US3**：接入覆盖审计、有限 Agent 工具、失败收敛和可重试/人工状态。
6. **US4**：正式保存文档块和定位关联数据，增加区域证据 API 和校对/审核 UI。
7. **US5**：完成 Shadow、灰度、默认切换、基准评测和回退验证。
8. **Polish**：更新 Overview/README、运行完整验证、回写 Issue 和提交。

## 必要复杂度

| 必要复杂度 | 为什么需要 | 已拒绝的简单方案及原因 |
| --- | --- | --- |
| 多解析器适配器 | 文本、表格、扫描和公式的失败模式不同 | 只替换 PyMuPDF 无法处理图像和表格 |
| Document IR | Markdown 不能稳定表达 bbox、表格单元和来源版本 | 只扩展 `paper_chunks` 会把展示文本和证据身份混在一起 |
| Claim 校验与覆盖审计 | “已有值有引句”不能证明没有漏值 | 只做二次 LLM 核对可能重复同一种错误 |
| 受控 PDF LLM | 跨页理解和复杂视觉需要多模态能力 | 让模型直接写库不可审计、不可回滚 |
| Shadow/灰度/回退 | 新解析器存在真实论文分布外风险 | 一次性替换旧链路会放大错误影响 |


## 本轮适配实现边界

T010/T011 使用 `pdf_parser_worker.py` 隔离重型 SDK，`structured_pdf.py` 统一输出映射。
默认 Docling CPU；MinerU basic OCR；调用方可用 ParseOptions 显式指定 MinerU 档位，
公开上传 API 尚未暴露这些细粒度选项。原生 PDF LLM、完整 Claim 提取、迁移和上线门禁
继续按后续任务实现，不能用本轮适配测试代替整条链路验收。T002 的人工标注基准是默认
上线门，独立适配器的实现和合成 PDF 验证可先行。
