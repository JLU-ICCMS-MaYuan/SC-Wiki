# 数据库初始化与迁移

## 功能说明

建立主业务数据库结构、应用 Alembic 版本迁移并幂等填充 118 个周期表元素。

## 当前行为

- `make deploy` 的新空库路径执行全部受测迁移分支，当前头为 `20260914_0052`、`20260918_0108`，并填充 118 个元素；只允许空库进入初始化，不使用 `create_all + stamp` 代替迁移。
- 便携包恢复后和普通启动前，共用 `scripts/local_deploy/schema.py` 检查全部 revision 及受测结构。恢复过程不升级源库、不重放旧迁移。便携实例的结构基线不表示现有开发库或其他机器已迁移，验证范围见 [#112](../../specs/112-portable-local-deployment/validation.md)。
- Docker Compose 定义 `frontend`、`goserver`、`python`、`mysql`、`redis`、`neo4j`、`qdrant` 七类服务，Go 服务依赖 MySQL 与 Redis 健康检查，Python 服务依赖 MySQL 与 Qdrant 健康检查。
- Go 服务从 `DATABASE_URL` 解析 MySQL DSN，缺少 `DATABASE_URL` 或 `JWT_SECRET_KEY` 会直接拒绝启动。
- Python 服务仍通过 `backend/database.py` 与 Alembic 使用 `DATABASE_URL`，并保留 `Base.metadata.create_all` 和周期表元素初始化脚本。
- Alembic 环境允许 `DATABASE_URL` 覆盖配置文件连接串。
- 本地 MySQL 当前迁移版本为 `20260917_0107` 与并行分支 `20260914_0052`。`0105` 新增可空的 `material_states.material_name VARCHAR(255)`；`0106` 允许 `superconductor_id` 为空以保存没有化学式的命名材料，不回填或改写历史数据。存在无化学式状态时拒绝直接降级恢复必填关联。热重载不会执行迁移，必须核验实际列；详见 [保存闭环与迁移验收](../../specs/103-property-evidence-review/material-name-save-flow.md)。论文上传模型包含唯一 `papers.upload_task_id`、多来源 `paper_files`、带来源文件和页码范围的 `paper_chunks`，以及永久 `paper_evidences`；`papers.admin_internal_note` 与面向上传者的 `review_comment` 分开保存。
- `20260911_0103` 在 `20260909_0099` 后新增 `property_evidence_checks`，保存物性核对的内容摘要、来源摘要、规则版本、结论、模型与理由；记录外键使用 `ON DELETE CASCADE`。迁移不扫描或回填历史证据，历史数据在后续提交或批准时按需核对。

- `20260915_0103` 和 `20260915_0104` 从 `20260911_0103` 增量新增科学临时核对、永久来源、结构提交来源与持久上传草稿四张表；不扫描或回填历史数据。并行迁移分支使用明确 revision 执行，不能假定工作区只有一个 head。
- 社区迁移 `20260917_0107` 依赖 `20260916_0106`，新增体系讨论空间、内容、点赞、举报、处理事件和站内通知六张表；不回填历史数据。SQLAlchemy 元数据由 Alembic 与初始化入口显式导入。2026-09-17 经用户确认，已应用至本地 `scwiki` 并保留并行分支 `20260914_0052`；运行中的社区读取接口、页面和实际数据库回滚写入检查通过。其他环境部署仍须单独核验；见[社区验收](../../specs/106-community-discussion/quickstart.md)。

## 工作流程

Docker 部署时先启动数据库、缓存、图数据库和向量数据库，再启动 Go 与 Python 服务；Nginx 前端将 `/api/` 和 `/health` 代理到 Go 服务，Go 服务将未匹配路由转发到 Python 服务。离线迁移仍通过 Alembic 和初始化脚本维护关系数据库结构。

## 约束

- Go 服务没有 SQLite fallback，生产或 Docker 环境必须提供 MySQL 格式 `DATABASE_URL`。
- Docker 部署文档要求手动导入 MySQL dump、Neo4j dump 和数据文件；本文不声明这些导入已经在当前环境执行。
- 自动 `create_all` 不等同于完整迁移流程，部署入口必须明确选择。

## 代码与测试

- `docker/compose.yaml`
- `docker/deploy/README.md`
- `docker/nginx.conf`
- `backend/main.py`
- `backend/scripts/init_db.py`
- `backend/database.py`
- `goserver/main.go`
- `alembic/env.py`、`alembic/versions/`
- `alembic/versions/20260820_0005_add_multifile_uploads.py`
- `alembic/versions/20260911_0103_property_evidence_checks.py`
- `tests/02_maintenance_and_verification/`

## 相关变更记录

- [Issue #103：物性证据保留、自动补证与人工裁决](../../specs/103-property-evidence-review/spec.md)

## 已知问题

- 多启动入口的数据库默认值和迁移行为尚未统一。
