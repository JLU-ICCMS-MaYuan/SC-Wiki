# 实施计划：超导参数提取与共用条件关联

**Issue**：[#139](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/139)

**日期**：2026-10-15

**Spec**：[spec.md](spec.md)，已确认；本计划为技术设计，未实施。

## 摘要

先将表格／表注包装成可定位的完整输入，复用领域提取和现有参数归一化。共享上下文模块联合读取 Methods 与局部例外，为多条结果提出有证据的共用关联。作者直接报告事实走原 Claim／覆盖链，推断关联走已有建议补空和人工核对链。复用记录 JSON、参数范围及扩展字段，不新增数据表、API 或模型配置。

## 技术上下文

- **语言与版本**：本地应用 Python 3.12、Node.js 22；前端 TypeScript ~5.6、React ^19.2。来源为 `docs/local-dev.md`、`frontend/package.json`；非本轮运行验证。
- **主要依赖**：FastAPI、Pydantic、SQLAlchemy、RQ／Redis、当前任务 LLM 客户端；PDF IR 继续使用既有互补解析，前端 MUI 与现有证据组件。
- **数据存储**：MySQL 现有 PropertyRecord JSON、证据关系及审核记录；任务运行制品保留上下文阅读与建议审计。无新增持久化表或自动迁移。
- **测试体系**：pytest、隔离 MySQL 集成、Vitest／Testing Library、真实浏览器核验；[quickstart.md](quickstart.md) 列出分层命令和限制。
- **目标平台**：现有 macOS 原生开发及项目 Linux 部署路径；不新增部署方式。
- **性能目标**：以 SC 的完整性、归属和保存一致性为硬指标，不预设未经测量的耗时保证。记录每阶段调用数、输入规模、耗时及可得 token 用量；缺失用量记未知而非零。
- **约束**：仅使用上传来源；共享参数仍需阶段和范围；不能覆盖人工值、放宽科学证据门或改已发布定义。
- **规模范围**：La–Sc–H 的 8 行首个真实样例，加跨页／跨方法／例外等合成反例；面向通用论文，不扩展到谱数字化或历史批处理。

## 质量门

| 约束来源 | 强制要求 | 设计如何满足 | 状态 |
| --- | --- | --- | --- |
| AGENTS.md | `mayuan`、精确暂存、自动提交、不推送 | 每次写入／提交前查分支；仅本 Spec 文档，本轮不写业务代码 | 本轮遵循 |
| Spec 最终确认 | 需求须先经用户全文确认 | 完整 Spec 展示后用户答复“是”，原文与确认记录已追加 | 已通过 |
| Overview | 数值不由全文汇总重写；逐条证据和覆盖 | 直接提取／机械组装保持职责；推断走建议阶段 | 设计符合，运行待验 |
| Spec FR-005～009 | 共用推断、局部例外及来源区分 | D3/D4 和附加元数据；不修改 `validate_claim` 为推断放行 | 设计符合，运行待验 |
| KISS／DRY／YAGNI | 复用参数、范围、建议及 JSON，不过度设计 | 单个共享上下文模块，无新表、模型供应商或公共 API | 设计审查通过 |
| 文档一致性 | FR/SC、数据、契约、任务和验证一致 | [analysis.md](analysis.md) 覆盖映射、路径及依赖核对 | 本轮机械检查及审阅 |
| 双向远程链接 | 平台实际可访问 Spec | 本地未推送，只登记相对路径，不伪造远程通过 | 未通过，需后续明确推送授权后验证 |
| 实施授权 | 规划确认不自动成为代码实现授权 | 本轮交付设计及 Tasks，任务不标完成 | 尚未进入实施 |

## 功能文档结构

```text
docs/specs/139-table-parameters-shared-methods/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/extraction.md
├── tasks.md
├── analysis.md
├── checklists/requirements.md
└── assets/IMG-001-upload-missing-parameters.png
```

## 源代码结构

拟新增：`backend/ingest/scientific_context.py`、`tests/fixtures/issue139/expected-table.json`、`tests/01_decentralized_uploading/test_issue139_scientific_context.py`、`test_issue139_table_parameters.py`、`test_issue139_workflow.py`、`test_issue139_persistence.py`、`issue139-parameters.test.tsx`。测试文件均位于所列测试目录，当前未创建。

主要现有触点：`backend/ingest/domain_extraction.py`、`scientific_contracts.py`、`tc_parameters.py`、`upload_jobs.py`、`upload_contracts.py`、`scientific_drafts.py`、`legacy_scientific_assembly.py`、`property_evidence.py`、`evidence_proposals.py`、`property_modules.py`；前端 `frontend/src/lib/tcParameters.ts`、`frontend/src/components/TcRecordFields.tsx`、`SchemaDrivenRecordForm.tsx`、`EvidenceWorkflow.tsx`；保存和导出复用 `backend/api/material_state_export.py` 及既有提交服务，必要改动由持久化回归决定。

**结构选择**：上下文阅读与关联生成集中在新模块；IR 表格包装仍由领域入口调用；模型输出、兼容转换、证据建议和业务存储的职责不交叉复制。只修现有表单绑定与理由呈现，不建立并行页面。

## 处理顺序

1. 核对源文件、版本及目标分支；保存修改前只读基线，人工核对原 PDF 的 8 行及 Methods。
2. 把表头／分组／脚注与表行联合输入提取，直接参数保持逐条来源，跨窗读取覆盖可审计。
3. 复用规范字段与范围契约，逐行确定性组装；兼容输入在边界改成相同记录表示。
4. 共享上下文为缺失字段生成阶段／范围关联，区分作者明确声明与 `paper_inference`。推断补空在最终直接 Claim 检查之后接入既有建议流程，保护已有值。
5. 保存记录级来源关联，重新计算内容／来源指纹；前端现有来源入口说明范围与局限。
6. 运行分层回归、真实模型解析、隔离 MySQL、浏览器与原 PDF 对照，最后回写 Overview 及 Issue 验收。

## 需求到设计的映射

| 来源 | 设计组件／决策 | 任务 | 验证方式 |
| --- | --- | --- | --- |
| FR-001 / US1 | 表格包、D1/D2 | T001、T003、T005 | 原 PDF 8 行、跨页表注 |
| FR-002 / US1 | 表行身份、近似和去重 | T004～T008 | 300 GPa 谐／非谐不合并 |
| FR-003 / US1 | D5 及现有 Tc 配对 | T004、T006、T008 | 明确反向配对／仅范围反例 |
| FR-004 / US1 | 统一字段、单位和幂等 | T004、T006、T007、T017 | 旧包装、别名、原单位与保存 |
| FR-005 / US2 | D1/D3、共用范围候选 | T003、T009、T010 | 多压力同方法及原文范围 |
| FR-006 / US2 | 阶段扩展及 D4 | T002、T009、T010 | QE／VASP／SSCHA 不混填 |
| FR-007 / US2 | 局部优先、缺口分类 | T009～T012 | 例外、冲突、未知范围 |
| FR-008 / US1～US3 | 来源关联元数据 | T002、T010、T013～T017 | 引句定位、推断标签、版本失效 |
| FR-009 / US3 | 现有建议及联合证据 | T013、T014、T018 | 数值和条件跨块仍正确核对 |
| FR-010 / US3 | 双入口、保存／导出与缓存 | T007、T011～T019 | Worker 到表单及持久化往返 |
| FR-011 / US1～US3 | 不编造、保留空值 | T004、T009、T012、T018 | 缺展宽、单位未知、不可读 |
| SC-001～SC-002 | Table 1 基线 | T001、T005～T008、T018、T019 | 8 行匹配、150 GPa 两端配对 |
| SC-003 | 共用与阶段核对 | T009～T012、T018、T019 | 错填和编造均为 0 |
| SC-004 | 反例矩阵 | T002～T019 | 独立预期与实际对比 |
| SC-005 | 持久化及浏览器 | T013～T019 | 保存重开、人工改值、无重复 |

## 阶段与依赖

先完成 T001～T003 的基线／来源基础，再串行交付 US1、US2、US3。每个故事都有测试与独立验收；US2 使用 US1 的稳定结果身份，US3 贯通已有路径。T017／T019 为最后持久化及浏览器验收。T020 回写文档，T021 为已授权推送后的远程核验，不自动执行。没有循环依赖，不安排并行 agent。

## 复杂度说明

| 必要复杂度 | 为什么需要 | 不采用的方案及原因 |
| --- | --- | --- |
| 全文窗口及表格包 | 仅一页重叠无法联系 Methods 与全部结果 | 只扩大字符上限仍可能漏读 |
| 条件阶段与范围关联 | 同论文有 850 eV／90 Ry／80 Ry 及多组网格 | 论文级条件广播会制造错误设置 |
| 直接事实与推断双路径 | 既有 Claim 不接受推断直接 validated | 放宽 Claim 门会把推断伪装为原文 |
| payload 来源元数据 | 关联理由需跨保存、返修及导出持久保留 | 只存运行目录会使正式记录失去依据 |
