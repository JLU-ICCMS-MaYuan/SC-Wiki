# 实施任务

输入：[Spec](spec.md)、[Plan](plan.md)、[Research](research.md)、[数据模型](data-model.md)、[契约](contracts/deployment.md)。

- [x] T001 核实源端版本、数据与发布身份，在 docs/specs/146-aliyun-production-deployment/validation.md 记录（源端实测及冻结清单见该文件）。
- [x] T002 [US3] 编写并验证 scripts/deploy.py 及 docker/compose.app.yaml、docker/compose.data.yaml、docker/compose.compute.yaml（真实独立启停和数据容器身份验证见 validation.md）。
- [x] T003 [US1] 实现认证连接、只读就绪、Caddy 和显式迁移，覆盖 backend/scripts/check_dependencies.py 与 goserver/（真实认证/schema 和 HTTPS 已验证；本次不需要升级 schema）。
- [x] T004 [US2] 实现 scripts/production_backup.py 的有清单备份、恢复、校验，验证对象元数据、TTL、空目标与失败保护（单元、隔离恢复和生产恢复证据见 validation.md）。
- [x] T005 [US2] 准备服务器与独立恢复演练，记录 validation.md。
- [x] T006 [US2] 排空写入、最终核对并复用已验证快照上传恢复与完整性核验，源数据保留，记录 validation.md。
- [ ] T007 [US1] [US3] 实际域名、业务、生命周期、持久化和资源验证，记录 validation.md。
- [ ] T008 更新 README.md、docker/deploy/README.md、相关 docs/overview/，提交并按授权发布，核实 Issue/Spec 双向链接。

依赖：T001 → T002/T003/T004 → T005 → T006 → T007 → T008；共享触点串行处理。所有勾选必须有真实证据。FR/SC 覆盖见 plan.md。

- [x] T009 [US1] [FR-008] 接入 text-embedding-v4 的可配置维度与分批调用，通过回归测试和服务器真实生成、保存、检索验证，记录制品与配置身份（见 validation.md 的最终运行容器记录）；不以此关闭 T007 的其他验收项。
- [x] T010 [FR-005] 为网络受限的同版本 Docker 归档提供差分转运；导出端与目标端均真实还原并严格校验完整 tar 摘要，再验证导入镜像身份（见 validation.md 的差分与镜像身份记录）。
- [x] T011 [US2/US3] 按用户指定的新名称迁移发布根与 SC-Wiki 持久目录，验证冷态完整性、业务清单、权限、重建和恢复服务，保留旧目录/旧卷及回退说明（见 validation.md 的 2026-10-22 迁移记录）。
- [x] T012 [US3] 按迁移后新增授权清理 /opt 下旧部署与临时目录、已停止演练容器；先保留迁移工作区并核验新副本和线上依赖，清理后验证 14 个服务身份与启动时间不变（见 validation.md 清理记录）。
