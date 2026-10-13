# 实施任务：统一业务文件存储

**输入**：[Spec](spec.md)、[Plan](plan.md)、[Research](research.md)、[数据模型](data-model.md)、[契约](contracts/storage.md)。各项已有局部实施证据，但尚未完成整项验收；进展与限制见 [验证记录](validation.md)。

## 阶段 1：准备

- [ ] T001 核验显式引用和由人工证据 row/item、候选附件元数据、审核快照任务 ID、富化结果论文 ID 派生的文件，建立 `backend/storage/reference_inventory.py`，覆盖本文数据模型全部载体及未分类文件阻断。
- [x] T002 在 `requirements.txt`、`docker/requirements.txt`、`goserver/go.mod` 中加入并锁定两语言 S3 SDK，验证兼容性，不升级核心依赖。证据：boto3 与 AWS SDK for Go v2 均固定版本；两种客户端在真实 Garage 2.4.1 上通过读写与冲突测试，见[验证记录](validation.md)。

## 阶段 2：基础能力

- [ ] T003 建立 `tests/02_maintenance_and_verification/test_file_storage_contract.py` 与 `goserver/storage/storage_test.go` 的双后端行为测试，含真实 S3、流式大文件、缺对象、错误认证、冲突及越界。
- [x] T004 在 `backend/storage/`、`goserver/storage/` 实现 FileRef、配置、local/S3、完整性校验与临时目录管理，满足存储契约。证据：本机实际切换后 74 个对象完整回读，Python 隔离业务与 Go handler 在真实 Garage/本地后端通过；见[验证记录](validation.md)。

## 阶段 3：US1——业务文件接入（P1）

- [ ] T005 [US1] 在 `tests/01_decentralized_uploading/test_file_storage_workflows.py` 建立上传、返修、人工证据、区域渲染、清理和越权端到端失败用例。
- [ ] T006 [US1] 改造 `backend/api/upload_tasks.py`、`backend/api/rag.py`、`backend/services/paper_revisions.py` 与 `backend/ingest/upload_tasks.py` 的引用读写及生命周期，保持 API 兼容。
- [ ] T007 [US1] 改造 `backend/ingest/upload_jobs.py`、`document_regions.py`、`manual_evidence.py`、`document_shadow.py` 及 T001 登记的其他消费者，使用 materialize 和不可变持久产物。
- [x] T008 [US1] 在 `goserver/handlers/account.go`、`public_profile.go`、`governance.go` 接入头像存储并在 `goserver/handlers/avatar_storage_test.go` 验证替换、越权、旧引用与失败清理。证据：隔离 SQLite + 本地与真实 Garage 后端的 handler 用例通过，替换和删除后桶内无残留对象；见[验证记录](validation.md)。
- [ ] T009 [US1] 在 `backend/ingest/upload_tasks.py` 和 `backend/services/paper_revisions.py` 收敛引用检查与清理并发控制，验证仍被正式论文/返修引用的对象不会删除。

## 阶段 4：US2——历史迁移（P1）

- [ ] T010 [US2] 在 `tests/02_maintenance_and_verification/test_file_storage_migration.py` 建立 MySQL/Redis/S3 历史夹具，包含没有 `stored_path` 字段的人工证据、候选附件、审核快照及富化结果，覆盖 TTL、缺失、越界、冲突、未分类文件、阶段中断与续跑。
- [x] T011 [US2] 实现 `backend/scripts/migrate_file_storage.py` 的 scan/copy/verify/switch/rollback，条件更新引用并保留源文件和脱敏清单。证据：2026-10-13 本机 MySQL/Redis/Garage 实例完成切换、切换前回退及再次切换；见 [验证记录](validation.md)。
- [x] T012 [US2] 按 `docs/specs/131-unified-file-storage/quickstart.md` 执行完整迁移和切换前回退，记录清单统计、内容摘要及故障证据。证据：74 个对象、21,056,060 字节与 28 处显式引用逐项核验，旧源文件保留；见 [验证记录](validation.md)。

## 阶段 5：US3——本地兼容（P2）

- [ ] T013 [US3] 在 `scripts/local_deploy/paths.py`、`storage.py`、`config.py` 适配规范键和本地存储检测，在 `tests/02_maintenance_and_verification/test_local_storage_compat.py` 验证原生启动及冻结恢复；S3 实例拒绝使用本地包命令。

## 最终阶段：验收与文档

- [ ] T014 完成 `docs/specs/131-unified-file-storage/quickstart.md` 的真实双后端矩阵，生成 `docs/specs/131-unified-file-storage/validation.md`，区分自动测试和人工验收。
- [ ] T015 使用 Overview Skill 更新 `docs/overview/01_Decentralized_Uploading_of_Superconductivity_Data/`、`docs/overview/02_Decentralized_Maintenance_and_Verification/` 和 `docs/overview/06_Researcher_Community_Forum/` 的相关文件及 `README.md`、`docker/deploy/README.md`，完成 #131 文档关闭门。

## 依赖与覆盖

T001/T002 → T003/T004 → US1 → US2/US3 → T014/T015。跨语言独立测试可分别开发；共享 Python 文件与迁移按序执行，不能按 `[P]` 暗示并发修改。同一对象存储与模型契约稳定后才能实施 #132/#133。

| 来源 | 任务 |
| --- | --- |
| FR-001、FR-002 | T001、T004、T006、T007、T008 |
| FR-003、FR-004 | T003、T005、T006、T008 |
| FR-005、FR-006 | T004、T007、T009 |
| FR-007、FR-008 | T010、T011、T012 |
| FR-009 | T004、T013 |
| FR-010 | T003、T010、T011、T014 |
| SC-001、SC-004 | T005、T008、T009、T014 |
| SC-002、SC-003 | T010、T012 |
| SC-005 | T013、T014 |

MVP 为 US1 的新文件完整闭环；生产已有数据切换必须连同 US2 完成，不允许把 MVP 当作历史数据已迁移。
