# 实施计划：跨机器解析与故障恢复

**Issue**：[ #133](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/133)

**日期**：2026-10-12

**输入**：[Spec](spec.md)、[Research](research.md)、[数据模型](data-model.md)、[执行契约](contracts/execution.md)、[迁移契约](contracts/compute-migration.md)。

## 技术上下文

Python 3.12、RQ 2.12.0/Redis 8.1.0 客户端、SQLAlchemy 2.0.52/MySQL、PyMuPDF、Docling 2.130.0、MinerU 4.0.6、GROBID 0.8.1 及现有多模型配置。不改变所选解析方案、覆盖检查和模型 API；依赖 #131 的文件接口、#132 的编排与认证。

目标为 Linux Docker 计算节点，保留本地原生及 macOS SpawnWorker 路径。使用 pytest、真实 Redis/RQ、MySQL/S3、浏览器工作流与三台独立主机；测试必须覆盖实际进程退出与持久化边界。

## 实现组织

- 新建 `backend/ingest/task_executions.py`，集中执行代次、租约、提交事务和 Redis 投影；新增 `task_execution_heads` 的模型及 Alembic 迁移。
- 改造 `upload_tasks.py`、`upload_jobs.py`、`property_evidence.py` 与 shadow/清理路径，所有共享副作用经过当前执行权检查。
- 上传解析与证据核对统一使用 FileRef 和 attempt 目录，解析器继续接收临时本地路径；运行元数据持久化与必需结果集合分开。
- `run_upload_workers.py` 增加执行续约、监督与恢复入口；复用现有 RQ 运行循环，不新建调度平台。API 与 Worker 共用执行状态契约版本。
- `backend/scripts/reconcile_task_executions.py` 负责补投、失联收敛、已提交结果同步；常规读取不增加跨数据库兜底分支。
- `document_regions.py` 保留网站按需渲染，经 #131 取得文件；运行时学习缓存移出源码写路径，使用共享 Redis 缓存，静态映射仍随制品。

## 需求映射

| 来源 | 设计 | 验证 |
| --- | --- | --- |
| FR-001、FR-002、FR-008 / US1 | FileRef、输入摘要、独立目录、计算组 | SC-001、SC-004；真实远程任务 |
| FR-003、FR-004、FR-006 / US1/US2 | 执行头、代次校验、事务提交、状态投影 | SC-002、SC-003；失败注入与并发 |
| FR-005、FR-007 / US2 | 租约、有限执行时间、reconcile、引用清理 | SC-004；断连、中断、恢复 |
| FR-009、FR-012 | 既有短期模型配置、脱敏身份日志 | SC-003、SC-004；过期配置及日志检查 |
| FR-010、FR-011 / US3 | 排空、三机切换与业务矩阵 | SC-005；真实部署与回退 |

## 阶段与共享触点

#131/#132 的已验证契约 → 执行模型与测试 → US1 远程文件链路 → US2 提交恢复 → US3 三机验收 → 文档。先核查全部中间写入点，再引入提交协议；不能只包住最外层函数而放任早期写入绕过 fencing。

`upload_jobs.py`、`upload_tasks.py`、`backend/models.py`、`backend/rag/config.py`、Python 依赖与 compute Compose 是跨 Feature 串行触点。前两个 Feature 完成后重新读取实际制品，不按旧任务勾选推断实现一致。

## 质量门

执行头只保存最小提交证明，避免复制完整任务平台；原有权限和正式提交所有权不变。真实 MySQL 行锁与进程故障测试不可由 SQLite/Mock 替代。单机容器分网络仅作为前置测试，三台主机没有验收就不关闭 Issue。模型有效性仍由原 Feature 管理，本次部署回归不等于科学质量提升。

## Documentation Impact

实现后回写上传解析、证据核对和部署 Overview，README/部署指南补充计算迁移及故障处理；记录真实版本与运行证据，未推送提交不得声称远端文档同步完成。
