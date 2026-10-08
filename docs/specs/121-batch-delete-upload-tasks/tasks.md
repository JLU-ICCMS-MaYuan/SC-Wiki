# 实施任务：上传解析记录支持多选批量删除

**输入**：[spec.md](spec.md)、[plan.md](plan.md)

**格式**：`- [ ] T### [P?] [US#?] 动作描述，包含准确文件路径`

## 阶段 1：准备

**目的**：确认实现所需的事实基础，不引入新依赖。

- [ ] T001 核对 `backend/ingest/upload_tasks.py` 中 `cleanup_transient_data`、`cleanup_unsubmitted_files`、`cleanup_duplicate_candidate`、`_delete_processing_job`、`submitted_paper_id` 的签名与行为，确认可直接组合

## 阶段 2：基础能力（后端删除语义）

**目的**：收敛单条删除语义，供单条与批量接口复用。

- [ ] T002 [P] 在 `backend/ingest/upload_tasks.py` 新增 `delete_task_record(task_id: str) -> str`：在 `upload_task_lock` 内——运行中状态先 `_delete_processing_job(state["job_id"])` 并置 `cancelled`；`submitted_paper_id` 非空时仅 `cleanup_transient_data(preserve_review_snapshot=True)`；否则执行 `cleanup_transient_data` + `cleanup_unsubmitted_files` + `cleanup_duplicate_candidate` + 证据删除（与 `cleanup_task_files` 一致）；锁超时抛出可识别异常
- [ ] T003 [P] 重构 `backend/api/upload_tasks.py` 的 `delete_upload_task`（L294）复用 T002 函数，保持现有 409 错误码 `UPLOAD_TASK_NOT_CLEARABLE` / `UPLOAD_TASK_PERSISTED` 对外行为不变

## 阶段 3：用户故事 1+2+3——批量删除接口（P1/P2）

**目标**：提供 best-effort 批量删除 API，覆盖任意状态记录。

**独立验收**：pytest 覆盖终态、运行中、submitted、越权、不存在、锁超时六类用例。

### 测试

- [ ] T004 [P] [US1/US2/US3] 新建 `tests/01_decentralized_uploading/test_issue121_batch_delete.py`，先写失败测试：终态批量删除成功；queued/extracting 记录删除后 RQ 作业移除且状态键清空；submitted 记录删除后 Paper 仍在、`result.json` 快照保留；越权与非法 ID 计入 `failed`；超过 100 条整批 413/400 拒绝

### 实施

- [ ] T005 [US1/US2/US3] 在 `backend/api/upload_tasks.py` 新增 `BatchDeleteRequest`（`task_ids: list[str]`，1~100 条）与 `POST /batch-delete` 路由：逐条 `_owned_state` 校验 + `delete_task_record`，收集 `deleted: [{task_id}]` 与 `failed: [{task_id, reason}]`，单条异常不中断整批
- [ ] T006 [US1/US2/US3] 运行 `pytest tests/01_decentralized_uploading/test_issue121_batch_delete.py` 与既有 `test_issue23_upload_lifecycle.py`、`test_issue35_cleanup_lifecycle.py` 确认新旧行为均通过

## 阶段 4：用户故事 1+2（前端多选 UI）（P1）

**目标**：列表支持勾选、全选、确认弹窗与结果反馈。

**独立验收**：Vitest 契约测试通过；手动验证勾选→确认→删除→刷新闭环。

### 测试

- [ ] T007 [P] [US1/US2] 新建 `tests/01_decentralized_uploading/upload-task-batch-delete.test.tsx`，先写失败测试：渲染复选框并可勾选；全选切换；选中计数；未选中时按钮禁用；确认弹窗显示数量；确认后调用批量接口并刷新；失败明细展示

### 实施

- [ ] T008 [US1/US2] 修改 `frontend/src/components/UploadTaskCenter.tsx`：新增 `selectedIds: Set<string>`（参照 `AdminPage.tsx` L143）、每行 MUI Checkbox（`onClick` 阻止冒泡，不影响卡片展开）、全选 Checkbox（头部，indeterminate 态）、选中计数 Chip、「批量删除」Button（禁用态）、MUI Dialog 确认弹窗、删除后 `await load()` 并用 Alert 展示 `deleted`/`failed` 结果
- [ ] T009 [US1/US2] 在 `frontend/src/i18n/zh/upload.ts` 与 `frontend/src/i18n/en/upload.ts` 新增键：`batchDelete`、`batchDeleteConfirmTitle`、`batchDeleteConfirmText`、`batchDeleteConfirmAction`、`batchDeleteDone`、`batchDeletePartialFailed`、`selectAll`、`batchDeleteFailed`（文案参照 `admin.ts` 风格）
- [ ] T010 [US1/US2] 运行前端契约测试与 `npm run build`（或项目等效命令）确认类型与构建通过

## 最终阶段：完善与跨故事事项

- [ ] T011 全链路手动自测：启动 backend + frontend，覆盖终态/运行中/submitted 三类记录的批量删除，核对 Redis 键、`upload_PDFs` 目录与 Paper 数据
- [ ] T012 使用 `big-project-overview-maintainer` 更新 `docs/overview/01_Decentralized_Uploading_of_Superconductivity_Data/pdf-ingestion.md`（批量删除接口与任意状态删除行为）
- [ ] T013 回写本文件复选框、更新 Issue #121 评论与关闭检查，按 AGENTS.md 多行格式提交 Git commit

## 依赖与执行顺序

- T001 无依赖；T002 → T003 → T005 → T006 串行（同文件或同语义链）。
- T004/T007 可与实现并行先行（失败测试）；T008–T010 依赖 T005 的接口契约。
- T011–T013 依赖全部前置任务。

## 需求覆盖

| 来源 | 任务 | 说明 |
|------|------|------|
| FR-001~004 / US1 / US2 | T007–T010 | 前端多选交互与确认闭环 |
| FR-005 / SC-003 | T002/T004–T006 | 批量接口与逐条结果 |
| FR-006 / US2 | T002/T004–T006 | 运行中先终止作业再清理 |
| FR-007 / US3 | T002/T004–T006 | submitted 保留论文与快照 |
| FR-008 / SC-004 | T004–T006 | 归属校验与越权用例 |
| FR-009 | T008 | 删除后刷新与结果反馈 |
| FR-010 | T009 | 中英文文案 |

## MVP 与增量策略

1. 完成阶段 1–3 后接口即可独立验收（可用 curl/pytest 验证）。
2. 阶段 4 交付用户可见交互，保持接口不变。
3. 最终阶段完成文档回写与 Issue 关闭。
