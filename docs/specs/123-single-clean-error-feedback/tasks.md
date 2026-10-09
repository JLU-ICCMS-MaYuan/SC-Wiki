# 任务拆解：#123 单条清理失败反馈与锁超时处理

## 阶段 1：缺陷修复（已全部完成）

- [x] T001 [P] `frontend/src/components/UploadTaskCenter.tsx`：单条清理处理函数增加 try/catch，失败时 `setError` 展示后端原因，成功后清除错误并刷新列表
- [x] T002 [P] `backend/api/upload_tasks.py`：单条 DELETE 捕获 `TimeoutError`，返回 409 `UPLOAD_TASK_BUSY`
- [x] T003 [P] `tests/01_decentralized_uploading/test_issue121_batch_delete.py`：新增锁超时返回 409 的回归用例
- [x] T004 [P] `tests/01_decentralized_uploading/upload-task-single-clean.test.tsx`：新增单条清理成功刷新与失败原因展示用例

## 阶段 2：文档回写

- [x] T005 [P] 新增本 Spec 目录并双向链接 Issue #123
- [x] T006 回写 `docs/overview/` 上传解析记录清理相关行为（pdf-ingestion.md 新增 #123 行为条目与变更记录链接）
