# 实施计划：上传解析记录支持多选批量删除

**GitHub Issue**：[#121](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/121)

**日期**：2026-10-08

**Spec**：[spec.md](spec.md)

## 摘要

在后端新增 `POST /api/upload-tasks/batch-delete` 接口，复用现有清理原语组合出"终止作业 → 清理状态/文件/索引"的单条删除函数，并对已持久化论文的记录保留审核快照；在前端 `UploadTaskCenter` 复用 AdminPage 的多选交互模式（复选框 + 全选 + 选中计数 + 确认弹窗），调用批量接口并展示逐条结果。

## 技术上下文

- **语言与版本**：Python 3.12+（FastAPI）；TypeScript + React 19 + MUI v7
- **主要依赖**：Redis（任务状态）、RQ（解析作业队列）、SQLAlchemy（Paper 持久化）、pytest（后端测试）、Vitest（前端契约测试）
- **数据存储**：Redis 键 `upload:{task_id}:state` + 用户索引 zset `upload:user:{user_id}:tasks`；文件目录 `data/upload_PDFs/{task_id}`、`data/review_artifacts/{task_id}`
- **测试体系**：`tests/01_decentralized_uploading/`（pytest + Vitest），本 Feature 新增 `test_issue121_batch_delete.py` 与前端契约测试
- **目标平台**：现有 Docker Compose 部署（backend + worker + frontend）
- **性能目标**：≤100 条记录的批量删除在数秒内完成（Redis 单键操作串行）
- **约束**：必须持有 `upload_task_lock` 防止与提交/清理并发冲突；禁止越权；禁止删除正式论文

## 关键技术决策

| 决策 | 选择 | 理由 | 备选方案 |
|------|------|------|----------|
| 批量接口形态 | 新增 `POST /api/upload-tasks/batch-delete`，请求体 `{ task_ids: string[] }` | DELETE 语义上不宜携带 body；与现有 `POST /cleanup` 风格一致 | 前端循环调用单条 DELETE——N 次往返且无法返回整批结果，弃用 |
| 运行中任务终止方式 | 在 `upload_task_lock` 内直接 `_delete_processing_job(job_id)` 并把状态置为 `cancelled`，随后立即清理 | 批量删除的语义是"立即清除"，等待 Worker 响应取消标志（`cancelling` 中间态）会让删除结果不可预期 | 复用 `/cancel` 的 202 异步取消——用户需二次操作才能删除，违背需求 |
| 已提交记录的处理 | `submitted_paper_id` 非空时仅执行 `cleanup_transient_data(preserve_review_snapshot=True)` | 与现有 `cleanup_upload_task` 对已持久化任务的处理完全一致（DRY） | 删除 Paper 记录——超出范围且有数据安全事故风险 |
| 删除逻辑复用 | 在 `backend/ingest/upload_tasks.py` 抽取 `delete_task_record(task_id)` 公共函数（锁内：运行中先终止 → 按是否持久化选择清理深度） | 单条 DELETE 与批量接口共享同一套语义（DRY）；`cleanup_task_files` 的三原语组合直接沿用 | 在 API 层内联写两份逻辑——重复且易漂移 |
| 失败语义 | best-effort，逐条 try/except，返回 `deleted` + `failed[{task_id, reason}]` | 与 Spec SC-003 一致；`TimeoutError`（锁超时）是可恢复错误，不应中断整批 | all-or-nothing——一条锁超时阻塞整批，体验差 |

## 质量门

| 约束来源 | 强制要求 | 设计如何满足 | 状态 |
|----------|----------|--------------|------|
| AGENTS.md | docs/ 简体中文；SOLID/DRY/YAGNI | 本文档与 spec/tasks 均中文；抽取公共删除函数；不做范围外功能 | 通过 |
| Overview（pdf-ingestion.md） | 已提交任务只做临时清理并保留审核快照 | FR-007 与决策第 3 条一致 | 通过 |
| Spec FR-008/SC-004 | 归属校验防越权 | 复用 `_owned_state`（本人或 admin） | 通过 |
| Spec FR-005/SC-003 | 逐条结果返回 | 响应体含 `deleted` 与 `failed` 明细 | 通过 |

## 源代码结构

```text
backend/
├── api/upload_tasks.py            # 新增 POST /batch-delete 路由与请求模型
└── ingest/upload_tasks.py         # 新增 delete_task_record 公共删除函数
frontend/
├── src/components/UploadTaskCenter.tsx  # 多选 UI、确认弹窗、结果反馈
└── src/i18n/{zh,en}/upload.ts           # 批量删除文案
tests/01_decentralized_uploading/
├── test_issue121_batch_delete.py        # 后端接口测试
└── upload-task-batch-delete.test.tsx    # 前端契约测试
docs/
├── specs/121-batch-delete-upload-tasks/ # 本 Spec 目录
└── overview/01_.../pdf-ingestion.md     # 行为回写
```

**结构选择**：删除语义收敛到 `ingest` 层单一函数（单一职责），`api` 层只做鉴权、参数校验与结果组装；前端只改 `UploadTaskCenter` 一个组件，i18n 键沿用 `upload.*` 命名空间。

## 需求到设计的映射

| 来源 | 设计组件/接口 | 验证方式 |
|------|---------------|----------|
| FR-001~004 / US1 / US2 | `UploadTaskCenter.tsx` 多选 UI + 确认弹窗 | `upload-task-batch-delete.test.tsx` |
| FR-005 / SC-003 | `POST /api/upload-tasks/batch-delete` 返回明细 | `test_issue121_batch_delete.py` |
| FR-006 / US2 | `delete_task_record` 锁内终止 RQ 作业 | 同上（queued/extracting 用例） |
| FR-007 / US3 | `submitted_paper_id` 分支保留快照 | 同上（submitted 用例，断言 Paper 仍在） |
| FR-008 / SC-004 | `_owned_state` 归属校验 | 同上（越权/不存在用例） |
| FR-009 | 删除后 `load()` 刷新 + 结果 Alert | 前端契约测试 |
| FR-010 | `zh/en upload.ts` 新增键 | 现有 i18n 契约测试（enum-labels 等）覆盖机制 |

## 阶段与依赖

1. 后端公共删除函数 `delete_task_record`（无外部依赖）
2. 批量删除路由 + 后端测试（依赖 1）
3. 前端多选 UI + i18n + 前端契约测试（依赖 2 的接口契约，可与 2 的测试并行编写）
4. Overview 回写与 Issue 关闭检查（依赖 1–3 全部验证通过）
