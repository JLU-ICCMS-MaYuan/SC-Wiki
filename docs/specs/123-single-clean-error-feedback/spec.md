# 上传解析记录单条清理失败反馈与锁超时处理

- **Issue**：[#123 上传解析记录单条「清理」失败时无任何反馈，锁超时被吞为 500](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/123)
- **类型**：type:bug
- **状态**：已实现（commit 510a43c，mayuan 分支）

## 背景与目标

「上传解析记录」列表中，单条「清理」按钮仅对终态记录（failed/duplicate/cancelled）渲染，调用 `DELETE /api/upload-tasks/{task_id}`。该链路存在两类缺陷：

1. 前端 `UploadTaskCenter` 的单条清理处理函数没有 try/catch，`api.del` 抛出的任何后端错误被静默吞掉，用户点击后记录不消失也无提示。
2. 后端未捕获 `delete_task_record` 抛出的生命周期锁超时（`TimeoutError`），以 500 返回。

本 Feature 目标：让单条清理的每一次失败都有明确反馈，锁超时有可理解的业务错误码，同时不改变 #121 确定的单条/批量删除语义分工。

## 需求与验收

- **FR-001**：单条清理被后端拒绝（409 `UPLOAD_TASK_NOT_CLEARABLE` / `UPLOAD_TASK_PERSISTED`、404 等）时，前端必须在列表顶部错误提示中展示后端原因。
- **FR-002**：生命周期锁超时时，单条 DELETE 必须返回 409 `UPLOAD_TASK_BUSY`「任务正被其他请求处理，请稍后重试」，而不是 500。
- **FR-003**：单条清理成功后列表刷新、记录消失；错误提示在下次成功操作后清除。
- **SC-001**：`tests/01_decentralized_uploading/test_issue121_batch_delete.py` 覆盖锁超时 → 409 `UPLOAD_TASK_BUSY`（已通过，9 passed）。
- **SC-002**：`tests/01_decentralized_uploading/upload-task-single-clean.test.tsx` 覆盖成功刷新与失败原因展示（已通过，2 passed）。

## 关键技术决策

| 决策 | 选择 | 理由 | 备选方案 |
|------|------|------|----------|
| 前端错误反馈方式 | 复用列表顶部 `Alert`（`setError`），与批量删除既有反馈一致 | DRY，交互模式统一 | 每条记录内联提示——引入新状态与布局改动，YAGNI |
| 锁超时错误码 | 新增 409 `UPLOAD_TASK_BUSY`，文案与批量接口的失败原因一致 | 409 表达可重试的业务冲突；避免 500 掩盖可恢复错误 | 沿用 500——用户无法理解，且前端无法区分 |
| 单条状态白名单 | 维持 {failed, duplicate, cancelled} 与 `UPLOAD_TASK_PERSISTED` 拒绝不变 | #121 Spec 明确范围外；批量删除已覆盖任意状态 | 放宽单条语义——与 #121 冲突，需另立需求 |

## 已知边界（记录但不实施）

单条清理与批量删除对「已持久化正式论文任务」的语义不对称：单条永久拒绝（409 `UPLOAD_TASK_PERSISTED`），批量可删除记录但保留论文与快照。该差异维持现状；如需对齐，另立 Issue。

## 假设与依赖

- `delete_task_record`、`upload_task_lock`、`submitted_paper_id` 等既有清理原语行为正确（#121 已验收）。
- 批量删除（#121）行为不变。

## 范围外事项

- 不放宽单条清理的状态白名单。
- 不修改 cleanup_at 自动清理倒计时与 Worker 定期清理逻辑。
- 不删除正式论文及其衍生数据。

## 澄清记录

### 2026-10-09

- 问：本缺陷是否由 #121 引入或与其冲突？ → 答：否。#121 明确「不改变单条取消/清理的现有交互与接口」，批量删除为增量功能；单条清理的静默失败在 #121 之前即存在，本次仅为缺陷修复。
