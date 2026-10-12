# 实施任务：三组服务独立编排

**输入**：[Spec](spec.md)、[Plan](plan.md)、[Research](research.md)、[数据模型](data-model.md)、[部署契约](contracts/deployment.md)。全部任务未执行。

## 阶段 1：准备与基础能力

- [ ] T001 在 `docker/deploy/release.example.json`、`docker/deploy/env/` 固化发布/实例配置契约；核验数据镜像与 MinIO 发行来源、许可、兼容性并解析实际 digest，不使用未核验版本。
- [ ] T002 在 `tests/02_maintenance_and_verification/test_deploy_cli.py` 建立角色、只读 plan、路径空格、失败码、隐私及生命周期范围测试。
- [ ] T003 在 `scripts/deploy.py` 实现本机分组命令、版本与数据身份校验、显式初始化及薄 Compose 调用。

## 阶段 2：US1——同机独立编排（P1）

- [ ] T004 [US1] 在 `tests/02_maintenance_and_verification/test_three_tier_compose.py` 建立三种拓扑配置与服务归属测试，更新 `tests/07_researcher_community_forum/test_news_compose.py`，避免继续匹配旧聚合文件。
- [ ] T005 [US1] 新建 `docker/compose.app.yaml`、`compose.data.yaml`、`compose.compute.yaml` 及跨机端口覆写文件，接入 #131 存储配置，显式卷身份和本机共享网络。
- [ ] T006 [US1] 在 `scripts/deploy.py` 实现单机组合与按组选取，按已验证接管流程退役 `docker/compose.yaml`，测试应用/计算操作不触碰数据容器与卷。

## 阶段 3：US3——连接、就绪与迁移边界（P2，US2 前置）

- [ ] T007 [US3] 在 `tests/02_maintenance_and_verification/test_remote_dependencies.py`、`goserver/cache/cache_test.go` 测试真实认证、错误 DSN、超时和日志脱敏。
- [ ] T008 [US3] 修改 `goserver/cache/cache.go`、`goserver/config/config.go` 和 `backend/rag/config.py`，统一 Redis URL、MySQL 同库校验、Qdrant 配置与本地兼容。
- [ ] T009 [US3] 新建 `backend/rag/qdrant_client.py`，改造 `vectordb.py`、`service.py`、`backend/scripts/build_summary_index.py` 等全部 Qdrant 入口，保留认证与超时一致性。
- [ ] T010 [US3] 实现 `backend/scripts/check_dependencies.py`、`goserver/main.go` 和 `backend/main.py` 的角色就绪与存活分离，完善三组 Compose 健康检查；测试 GROBID 故障不阻断网站登录。
- [ ] T011 [US3] 在 `backend/scripts/run_migrations.py`、`scripts/deploy.py` 实现显式 schema 迁移与只读启动检查，验证未知基线、多个 head 与既有确认门，不改变本地旧入口语义。

## 阶段 4：US2——迁出数据组（P1）

- [ ] T012 [US2] 在 `tests/02_maintenance_and_verification/test_data_group_migration.py` 建立旧卷接管、目标非空、版本冲突、备份损坏、TTL 及恢复中断验证。
- [ ] T013 [US2] 在 `docker/deploy/data-migration.md` 与 `scripts/deploy.py` 落实预检、清单校验和可续跑记录；引擎备份恢复使用经演练的原生命令，不复制运行中裸数据目录。
- [ ] T014 [US2] 按 `docs/specs/132-three-tier-deployment/quickstart.md` 在真实两机私网执行数据迁移、全数据完整性核验和切换前回退，保存证据。

## 最终阶段：回归与文档

- [ ] T015 在 `tests/02_maintenance_and_verification/test_local_deployment.py`、`test_mac_native.py` 运行相关原生回归，验证生产工具未改变本地端口/配置/生命周期。
- [ ] T016 完成 `docs/specs/132-three-tier-deployment/quickstart.md` 矩阵并新增 `validation.md`，记录 digest、schema、网络证据、未执行项；使用 Overview Skill 更新部署/迁移 Overview、`README.md`、`docker/deploy/README.md` 并同步 #132。

## 依赖与覆盖

#131 → T001～T003 → US1 → US3 → US2 → 回归/文档 → #133 三机验收。US3 的检查是 US2 安全迁移前置，优先级不表示可以跳过。共享 Compose、客户端和迁移文件串行修改。

| 来源 | 任务 |
| --- | --- |
| FR-001、FR-002、FR-003 | T002、T003、T004、T005、T006 |
| FR-004、FR-005 | T005、T007、T008、T009、T010 |
| FR-006 | T007、T010、T011 |
| FR-007、FR-011 | T001、T003、T011 |
| FR-008、FR-009 | T003、T012、T013、T014 |
| FR-010 | T015 |
| FR-012 | T002、T003、T007、T016 |
| SC-001 | T004、T006 |
| SC-002 | T004、T014 |
| SC-003 | T007、T010、T011 |
| SC-004 | T012、T014 |
| SC-005 | T001、T014、T015、T016 |

MVP 为同机三个项目的可组合部署，不能因此关闭真实两机迁移验收。三机配置就绪不等于 #133 的业务运行验收通过。
