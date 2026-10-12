# 实施任务：跨机器 PDF 解析与故障恢复

**输入**：[Spec](spec.md)、[Plan](plan.md)、[Research](research.md)、[数据模型](data-model.md)、[执行契约](contracts/execution.md)。全部任务未执行。

## 阶段 1：准备与基础能力

- [ ] T001 审计 `backend/ingest/upload_jobs.py`、`property_evidence.py`、`document_shadow.py`、`upload_tasks.py`、`scientific_evidence.py` 及其调用方的所有持久副作用，将执行权检查点登记在 `docs/specs/133-remote-pdf-workers/validation.md` 的待验证清单中。
- [ ] T002 在 `tests/01_decentralized_uploading/test_task_execution_heads.py` 建立真实 MySQL 并发、租约、取消/提交竞争和 stale attempt 测试。
- [ ] T003 在 `backend/models.py` 与 `alembic/versions/` 新增执行头模型及独立迁移，在 `backend/ingest/task_executions.py` 实现事务、代次与租约控制。

## 阶段 2：US1——跨机文件与结果链路（P1）

- [ ] T004 [US1] 在 `tests/01_decentralized_uploading/test_remote_pdf_workflow.py` 建立真实 Redis/MySQL/S3 与隔离 API/Worker 进程测试，禁止共享业务目录。
- [ ] T005 [US1] 改造 `backend/ingest/upload_tasks.py`、`backend/api/upload_tasks.py`、`backend/api/evidence.py` 的当前代次创建、确定性投递和内部消息；升级 `backend/ingest/upload_contracts.py` 状态版本并实现停机旧状态迁移。
- [ ] T006 [US1] 在 `backend/ingest/upload_jobs.py`、`property_evidence.py`、`document_shadow.py` 使用输入 FileRef、独立目录和产物 manifest，接入 #131 materialize。
- [ ] T007 [US1] 在 `backend/ingest/task_executions.py`、`scientific_evidence.py` 和 T001 全部写入点接入执行权校验，完成对象先保存、业务结果与执行标记同事务、Redis 后投影的协议。
- [ ] T008 [US1] 在 `backend/ingest/document_regions.py`、`document_run_metadata.py`、`prop_names.py` 及相关映射缓存入口落实网站文件读取、最小运行身份记录和可重建缓存边界。

## 阶段 3：US2——故障与幂等恢复（P1）

- [ ] T009 [US2] 在 `tests/01_decentralized_uploading/test_remote_worker_failures.py` 注入强制退出、重复消息、旧代次回写、对象部分失败、MySQL/Redis 断连与取消竞争。
- [ ] T010 [US2] 在 `backend/scripts/run_upload_workers.py`、`backend/rq_runtime.py` 实现续约、有限执行时间与监督恢复，保留 macOS SpawnWorker 分支。
- [ ] T011 [US2] 新建 `backend/scripts/reconcile_task_executions.py`，实现 check/apply、pending 补投、失联失败及 committed 投影，不自动重做失败模型任务。
- [ ] T012 [US2] 在 `backend/ingest/upload_tasks.py`、`document_shadow.py` 和清理任务中落实 attempt/当前引用保护与幂等清理，验证取消、返修和正式论文不受误删。
- [ ] T013 [US2] 在 `backend/ingest/upload_jobs.py`、`property_evidence.py` 与相关测试中验证临时模型配置归属、失效提示、无秘密产物和脱敏日志。

## 阶段 4：US3——迁出计算组（P2）

- [ ] T014 [US3] 在 `docker/compose.compute.yaml` 与 `docker/deploy/compute-migration.md` 落实监督命令、GROBID 配置、队列排空和单一延迟调度者，保持 #132 编排契约。
- [ ] T015 [US3] 按 `docs/specs/133-remote-pdf-workers/quickstart.md` 完成单机、真实两机、真实三机矩阵，同一版本验证完整业务与计算迁移/回退。

## 最终阶段：回归与文档

- [ ] T016 运行 `backend/tests/test_upload_workflow.py`、`test_upload_jobs.py`、`test_paper_revisions.py` 及 #35/#109/#114 相关测试、Go/API/前端和原生 Worker 回归，在 `docs/specs/133-remote-pdf-workers/validation.md` 汇总证据与未验收项。
- [ ] T017 使用 Overview Skill 更新 `docs/overview/01_Decentralized_Uploading_of_Superconductivity_Data/` 与部署运行 Overview、`README.md`、`docker/deploy/README.md`，完成 #133 关闭门并逐项核对 Epic #130 的剩余条件。

## 依赖与覆盖

#131/#132 → T001～T003 → US1 → US2 → US3 → 回归/文档。事务与共享写入改造必须串行；跨机器演练之前先通过隔离进程故障矩阵。MVP 为远程正常链路，但生产切换必须同时完成 US2，不能在重复执行保护缺失时上线。

| 来源 | 任务 |
| --- | --- |
| FR-001、FR-002 | T004、T005、T006 |
| FR-003、FR-004 | T001、T002、T003、T007、T009 |
| FR-005 | T009、T010、T011 |
| FR-006 | T002、T005、T007、T012、T016 |
| FR-007 | T006、T009、T012 |
| FR-008 | T008、T014、T015 |
| FR-009 | T005、T013 |
| FR-010、FR-011 | T014、T015、T016 |
| FR-012 | T008、T013、T016 |
| SC-001 | T004、T015 |
| SC-002、SC-003 | T002、T007、T009 |
| SC-004 | T009、T010、T011、T012、T013 |
| SC-005 | T014、T015、T016 |
