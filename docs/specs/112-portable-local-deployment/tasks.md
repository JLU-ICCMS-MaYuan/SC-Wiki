# 实施任务：跨机器本地部署与数据打包

**输入**：[Spec](spec.md)、[Plan](plan.md)、[Research](research.md)、[数据模型](data-model.md)、[CLI](contracts/cli.md)

**关联 Issue**：[ #112](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/112)

本轮完成规划，以下全部为尚未执行的实现与验收任务。复选框只记录技术交付，Issue 是协作状态来源。

## 阶段 1：准备与技术验证

- [x] T001 核验并固定 `scripts/local-deploy-versions.json` 的官方下载、校验和、镜像摘要、Conda 包版本和受测迁移头集合；在隔离环境证明 Python 3.12、Node 22、Go、Java 和数据库组合可安装，不从源机器完整环境冻结无关包。
- [ ] T002 在 `scripts/local_deploy/paths.py` 登记 MySQL、Redis 草稿、解析产物、结构候选的文件字段与业务指纹约束；与 `backend/models.py`、`backend/api/upload_tasks.py` 和数据目录写入点交叉核对，发现遗漏先更新本 Feature 数据模型。

## 阶段 2：共享基础能力

- [x] T003 在 `tests/02_maintenance_and_verification/test_local_deployment.py` 建立命令、配置解析、路径越界、包清单、状态恢复的行为测试；测试只操作临时目录和显式测试实例。
- [ ] T004 在 `scripts/local_deploy/environment.py`、`scripts/locallydeploy.sh` 实现系统预检、Conda 多前缀发现、私有 Miniforge 引导和环境兼容检查，覆盖无环境/已有环境/多候选三类情况。
- [x] T005 在 `scripts/local_deploy/config.py` 实现不执行 shell 的 dotenv 解析、本机随机凭据、URL 编码和已有配置保护；让 `scripts/lib-local.sh` 共用已解析环境，不打印凭据。
- [x] T006 在 `scripts/local_deploy/state.py`、`scripts/local_deploy/bundle.py` 实现操作锁、阶段状态、目录归属、摘要与包格式校验、流式归档校验和原子发布。

## 阶段 3：US1——部署新实例（P1）

**目标**：系统前置条件就绪后，无旧 `.env` 和 Conda 环境也能准备本地服务。

**独立验收**：在空目标运行部署，数据库结构和基础元素完整，服务可访问，第二次运行保留配置。

- [ ] T007 [US1] 在 `tests/02_maintenance_and_verification/test_local_deployment.py` 增加无 Conda、兼容环境复用、版本冲突、配置特殊字符、端口占用、离线/下载损坏和空间不足测试。
- [ ] T008 [US1] 在 `scripts/local_deploy/environment.py`、`scripts/setup-local.sh` 实现固定依赖安装与校验、Python 关键模块导入、pip check、npm ci、Go 模块验证和 GROBID Docker 预检；旧 setup 委托共享安装逻辑。
- [x] T009 [US1] 在 `backend/scripts/run_migrations.py` 实现显式空库初始化与便携实例只读 schema 核验；调整 `tests/02_maintenance_and_verification/test_fresh_mysql_schema.py` 的单头假设，并在真实空 MySQL 上执行全部受测 revision 和元素初始化。
- [x] T010 [US1] 在 `scripts/local_deploy/cli.py`、`scripts/dev.sh`、`scripts/lib-local.sh` 实现统一环境路径、进程归属检查、便携实例启动路径和回环监听；未知端口占用不能当成本项目健康实例。
- [x] T011 [US1] 在 `Makefile`、`scripts/locallydeploy.sh` 接入 locallydeploy、CHECK_ONLY 和稳定报告；缺初始化的 start/setup 错误改为新入口指引，报告空实例管理员创建方法。

## 阶段 4：US2——生成迁移包（P1）

**目标**：导出一致、完整、不含外部凭据的源码与数据包。

**独立验收**：使用含账户、表单、审核、附件、图、向量和未提交草稿的测试实例生成包，所有清单和摘要通过。

- [ ] T012 [US2] 在 `tests/02_maintenance_and_verification/test_local_deployment.py` 增加活动/排队/延迟重试作业阻断、停写失败、进程状态恢复、空集合与不可达区分、脏源码阻断测试。
- [x] T013 [US2] 在 `scripts/local_deploy/storage.py`、`scripts/dev.sh` 实现 300 秒宽限期、应用/新闻调度/Worker 停写和原状态恢复；禁止复用强杀活动任务或自动迁移源库的路径。
- [x] T014 [US2] 在 `scripts/local_deploy/storage.py` 实现 MySQL 全业务库逻辑导出、对象/结构/revision 清单、Neo4j 业务 dump、Qdrant 集合快照与别名；源结构不兼容或组件失败必须阻断发布。
- [x] T015 [US2] 在 `scripts/local_deploy/storage.py`、`scripts/local_deploy/paths.py` 实现 Redis 状态/草稿白名单、有效期、文件引用登记、凭据排除和原路径映射；以植入的假密钥检测包与日志，禁止输出真实凭据。
- [x] T016 [US2] 在 `scripts/pack.sh`、`scripts/local_deploy/bundle.py`、`Makefile` 实现干净 HEAD 源码归档、OUTPUT 参数、完整清单和原子发布；更新 `.gitignore` 排除 `.deployment/` 制品，明确不提交数据包。

## 阶段 5：US3——恢复与故障重试（P1）

**目标**：不同用户名/路径恢复，同包重跑保留数据，任何失败不覆盖原有实例。

**独立验收**：固定包在干净目标真实导入；登录、表单、审核、附件和草稿通过页面/API 验证。

- [ ] T017 [US3] 在 `tests/02_maintenance_and_verification/test_local_deployment.py` 增加损坏包、恶意路径、代码不匹配、既有数据、配置保留、多头/未知 revision、过期草稿和各阶段中断测试。
- [x] T018 [US3] 在 `scripts/local_deploy/storage.py` 实现临时实例原生恢复、MySQL 对象 DEFINER 映射、Neo4j 新认证、Qdrant 别名与配置恢复、Redis 有效业务状态恢复；不加载旧队列或系统认证数据。
- [ ] T019 [US3] 在 `scripts/local_deploy/paths.py` 实现只针对登记字段的路径转换和引用文件校验，覆盖持久草稿与结构候选；证明正文、证据、指纹、审批和历史记录未被非预期修改。
- [ ] T020 [US3] 在 `scripts/local_deploy/cli.py`、`scripts/local_deploy/state.py` 实现包自动发现/BUNDLE、空目标保护、提升前后中断恢复和幂等重跑；恢复完成后的重跑不按初始行数要求重导。
- [x] T021 [US3] 在 `scripts/local_deploy/cli.py` 实现结构/数据清单比对、数据库认证查询、真实 HTTP 链路与 Worker 注册验证，输出基础部署和 AI/SMTP 外部能力的分项报告。

## 阶段 6：跨故事验证与文档

- [ ] T022 在 `tests/02_maintenance_and_verification/local-deploy-roundtrip.sh` 建立真实 MySQL/Redis/Neo4j/Qdrant 的隔离导出恢复演练，覆盖换用户名/路径、空数据库、已存在环境、故障注入和源码归档无 .git 的部署。
- [ ] T023 按 `docs/specs/112-portable-local-deployment/quickstart.md` 完成 Ubuntu 22.04 与 WSL2 干净环境验收，记录机器/源码/包版本、实际服务与页面检查结果；未执行的外部调用明确保留未验收。Ubuntu 24.04 按用户要求不再作为必需验收项。
- [x] T024 使用 Overview 维护技能更新 `docs/overview/02_Decentralized_Maintenance_and_Verification/deployment-and-runtime.md`、`database-initialization-and-migrations.md`、`data-import-and-export.md` 及相关入口；同步 `README.md` 和 `docs/local-dev.md`，仅描述已实现行为。
- [ ] T025 对照 `docs/specs/112-portable-local-deployment/` 全部需求检查实现和证据，同步 #112 验收项及 Documentation Impact；用户已明确授权先按现有验证提交本次实现，剩余验收继续追踪，满足关闭条件后再关闭 Issue。

## 依赖与执行顺序

- T001–T002 先核验事实，T003–T006 建立共享基础。
- US1 依赖基础；US2 依赖共享基础及 US1 的实际服务能力；US3 依赖 US1、US2 的包契约。
- 同一 `storage.py`、`cli.py`、`dev.sh`、Makefile 或测试文件的任务串行，不标注可并行。
- 测试与文档审查可以在相应接口稳定后独立运行，但本规划没有授权调用多 Agent。
- 下载版本、完整迁移、原生恢复或真实验收有阻塞时，保持关联任务未完成，不用 mock 测试替代。

## 需求覆盖

| 来源 | 任务 | 说明 |
| --- | --- | --- |
| FR-001 | T010–T011、T016 | 两个入口及旧命令指引 |
| FR-002 | T003–T004、T007、T017 | 平台、工具、权限、网络、端口、空间 |
| FR-003 | T004、T007–T008 | 环境发现、复用和创建 |
| FR-004 | T001、T008、T022 | 固定依赖与实际安装 |
| FR-005 | T005、T007、T020 | 安全配置与原配置保护 |
| FR-006 | T006、T016–T017 | 源码、格式与完整性 |
| FR-007 | T014、T018、T022 | 全 MySQL 业务库及对象 |
| FR-008 | T014–T015、T018–T019 | 图、向量、草稿和附件 |
| FR-009 | T012–T013、T022 | 停写、活动作业、恢复运行状态 |
| FR-010 | T005、T015、T018 | 凭据排除与业务账号保留 |
| FR-011 | T017–T020 | 空目标及重复执行 |
| FR-012 | T009、T014、T017–T018 | 多分支和实际结构 |
| FR-013 | T002、T015、T019 | 字段级路径转换 |
| FR-014 | T006、T017、T020 | 中断和阶段记录 |
| FR-015 | T010、T021–T023 | 实际健康与能力报告 |
| FR-016 | T009–T011、T022 | 空库与管理员引导 |
| FR-017 | T003、T007、T012、T017、T022–T023 | 行为测试与真实演练 |
| SC-001 | T004、T008–T011、T023 | 干净机器单命令部署 |
| SC-002 | T014–T015、T018–T019、T021–T022 | 数据清单及完整性 |
| SC-003 | T019、T022–T023 | 换路径后业务可用 |
| SC-004 | T005–T007、T017、T020、T022 | 不覆盖、幂等和失败保护 |
| SC-005 | T005、T015、T018、T022 | 假密钥探针验证 |
| SC-006 | T023–T025 | 真实验收与文档关闭门槛 |

## MVP 与增量策略

US1 可独立验收安装能力；但本 Feature 的最小完整交付包含 US1–US3，不能只实现环境安装就宣称满足用户的搬迁需求。首版完成后再另开需求考虑离线包、ARM 或跨版本升级。


## 2026-09-21 实施证据与剩余工作

已完成项的证据集中于 [验证记录](validation.md)，实现覆盖命令入口、环境安装器、
安全配置、真实多头初始化、四类存储导出/恢复、原状态恢复及文档。
T001 的“组合可安装”由全新临时 Conda 环境和官方下载校验证明，不能据此勾选 T023。
T019 已通过返修基线与定向字段转换回归，仍需全部结构候选及审核指纹样本。
T022 的完整 CLI 演练使用自动端口与人工数据，尚不能替代跨用户名和完整故障注入。
T004/T007/T008/T012/T017 的剩余项以实际矩阵为准，不因相关代码已经存在而全部勾选。

- [ ] T026 [收敛] 补齐无 Conda 完整入口、环境冲突/低空间/下载中断及各恢复阶段故障注入；修复实测缺陷并保留真实日志，不只做静态断言。
- [ ] T027 [收敛] 在干净 Ubuntu 22.04 / WSL2 和不同用户名实例补齐 T023；Ubuntu 24.04 验收已按用户要求取消，其镜像拉取失败不再是提交阻塞。
- [ ] T028 [收敛] 扩展完整 CLI 人工样本至审核历史、结构候选附件下载、所有科学核对与历史指纹，补齐 T002/T019/T022 的业务验收。

## 阶段 7：本机 Docker 前置失败收敛

- [x] T029 [US1] 在 `scripts/local_deploy/environment.py`、`cli.py` 补充预检处理建议、错误码及真实环境检查状态；在 `tests/02_maintenance_and_verification/test_local_deployment.py` 验证 Docker 缺失/不可用时普通与只读入口均不写运行文件，并补充超时、端口冲突、低空间和损坏/中断下载保护。来源 FR-002/014/017、T004/T007/T026 的部分缺口；证据见 [本次验证](validation.md#docker-前置失败回归2026-09-21)。

本轮不勾选 T004/T007/T008/T022/T023/T026：无 Conda 完整安装、真实存储及全故障矩阵
仍未在当前机器完成。GitHub Issue 的开放状态与原验收项保持不变。
