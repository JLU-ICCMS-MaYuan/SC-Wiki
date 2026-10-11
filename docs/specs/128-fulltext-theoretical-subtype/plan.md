# 实施计划：理论二级类型全文归纳

**GitHub Issue**：[#128](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/128)
**日期**：2026-10-11
**Spec**：[spec.md](spec.md)；[研究](research.md)、[数据契约](data-model.md)、[任务](tasks.md)、[验收路径](quickstart.md)。

## 摘要

上传汇总继续处理其他字段，理论二级类型由独立全文分类器覆盖。分析由服务端持有，与可编辑的分类值分开；来源核对使用归纳理由和定位片段。现有 H3S 草稿采用单任务重跑，提交后沿用现有正式来源与审核链路。

## 技术上下文

| 项目 | 当前事实 |
|---|---|
| 语言与版本 | 本机验收环境为 Python 3.12、Node.js 26；后端 FastAPI/SQLAlchemy，前端 React/TypeScript/Vite |
| 主要依赖 | 当前 LLM JSON 调用、正文/附件解析、科学来源核对、Redis 上传任务、MySQL 论文及核对记录 |
| 数据存储 | 草稿由 Redis 保存并可由 `ScientificUploadDraft` 恢复；正式值沿用 `papers.theoretical_subtype`，来源沿用科学核对和正式来源表 |
| 测试体系 | `pytest`、Vitest、隔离 Chromium 脚本；命令与预期结果见 [quickstart.md](quickstart.md) |
| 目标平台 | 现有上传 Worker、Python API、上传与审核页；不新增服务或数据库迁移 |
| 规模与性能 | 一次可容纳时提供全部有效正文；超出来源批次容量时逐批阅读并综合全部批次，不设固定页数上限 |
| 安全约束 | 客户端只能编辑当前分类值；PUT 不能覆写服务端分析；定向重跑保护人工改值 |

## 质量门

| 来源 | 强制要求 | 设计与验证 | 当前状态 |
|---|---|---|---|
| FR-001、FR-002、FR-005 | 全文贡献分类、失败留空 | 正文与附件输入，长文逐批综合；三类和空值测试 | 局部测试及真实 H3S 已通过 |
| FR-003、FR-004、#109 | 来源可定位，归纳不冒充逐字事实 | 当前值及来源版本绑定；侧栏专用提示 | 来源、组件及已登录 H3S 页面验收已通过 |
| FR-006、AGENTS.md | 保护人工改值和其他核对 | 单任务锁、来源重读、字段级失效 | 定向重跑与局部测试已通过 |
| FR-007、SC-003 | 提交及正式审核来源持久化 | 现有事务转接来源；仍需端到端核验 | **部分通过：真实正式路径待验收** |
| AGENTS.md | 仅在 `mayuan` 分支提交本次文件 | 修改前查分支；逐文件暂存与复查 | 提交前复核 |

## Feature 文档结构

`spec.md` 定义目标；`research.md` 记录取舍；`data-model.md` 与 `contracts/classification.md` 说明状态和接口边界；`tasks.md` 追踪工作；`quickstart.md` 提供复跑路径与已有证据；`checklists/requirements.md` 检查需求质量。

## 源代码结构与职责

| 路径 | 职责 |
|---|---|
| `backend/ingest/theoretical_subtype.py` | 收集正文/附件、分类、定位引句及单任务重跑 |
| `backend/ingest/upload_jobs.py` | 汇总后调用分类器并覆盖候选汇总值 |
| `backend/api/rag.py` | 草稿 PUT 保持服务端分析所有权；提交事务转接上传核对 |
| `backend/ingest/property_evidence.py`、`backend/ingest/scientific_evidence.py` | 字段身份、支撑校验、核对保存与正式来源转接 |
| `backend/services/paper_revisions.py` | 返修草稿拒绝客户端伪造的分析对象 |
| `frontend/src/components/UploadTaskEditor.tsx`、`EvidenceWorkflow.tsx`、`frontend/src/pages/AdminPaperEditPage.tsx` | 编辑当前值、显示失败原因、代表片段与综合理由 |
| `scripts/reclassify-theoretical-subtype.py` | 仅指定任务并核对文件名后重判旧草稿 |

**结构选择**：分类、草稿写入、来源核对和 UI 分别沿用现有职责，不增设第二套分类表或新公开路由。

## 需求到设计的映射

| 来源 | 设计组件或契约 | 验证方式 |
|---|---|---|
| US1、FR-001、FR-002、FR-005、SC-001、SC-002 | `theoretical_subtype.py`、`upload_jobs.py` | H3S 真实模型、三类/空值和多批次测试 |
| US2、FR-003、FR-004、SC-003 | 草稿分析、字段哈希、证据侧栏 | Methods-only/失配定位测试、组件与浏览器夹具 |
| US3、FR-006、SC-004 | 单任务锁、原 AI 值比较、字段级来源版本 | 定向重跑、人工改值与其他字段哈希测试 |
| FR-007、SC-003 | `transfer_result`、提交事务与正式来源 | 隔离转接测试已通过；正式路径验收仍待完成 |

## 阶段与依赖

1. 建立 Spec、接口与需求检查表，核对现有解析和来源边界。
2. 实现并验证 US1 的全文分类，再接入 US2 的字段来源和 UI。
3. 在前两项可靠后执行 US3 的 H3S 定向重跑。
4. 核对提交、审核、浏览器与正式来源；缺少正式端到端证据时 #128 保持开放。

## 复杂度说明

| 必要复杂度 | 原因 | 未采用的简单方案 |
|---|---|---|
| 长文逐批阅读再综合 | 一次上下文放不下时仍须覆盖全文 | 固定页数或字符前缀会漏掉后文贡献 |
| 字段级分析身份与来源转接 | 用户改值和正式文件 ID 会变化 | 全局规则升版会使无关核对过期 |
| 单任务定向重跑 | 当前 H3S 可能已有人工编辑 | 批量重算历史论文超出范围 |

本次不修改 `papers` Schema，不重跑其他论文，也不覆盖其他字段已完成的核对。
