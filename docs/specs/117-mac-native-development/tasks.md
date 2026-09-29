# 实施任务：Mac 原生本地开发

输入：[spec.md](spec.md)、[plan.md](plan.md)、[research.md](research.md)、[data-model.md](data-model.md)、[命令契约](contracts/cli.md)。

## 阶段 1：准备

- [x] T001 完成 docs/specs/117-mac-native-development/ 的需求、设计和覆盖分析。

## 阶段 2：基础能力

- [x] T002 在 tests/02_maintenance_and_verification/test_mac_native.py 覆盖命令路由、原生进程归属和平台清单等故障边界。

## 阶段 3：US1 原生开发（P1，MVP）

- [x] T003 [US1] 实现 Makefile.mac、Makefile、scripts/lib-local.sh、scripts/dev.sh 及 scripts/local_deploy/ 平台适配，验证真实服务和源码重载。

## 阶段 4：US2 部署与冻结（P1）

- [x] T004 [US2] 复用 scripts/local_deploy/cli.py 的部署/冻结保护，完成预检、冻结恢复验证并写入 validation.md。

## 阶段 5：US3 清理旧环境（P2）

- [x] T005 [US3] 在 .local/backups/ 保存旧实例逻辑备份并恢复核对，清理 .local/mac-deploy/、.local/scwiki-runtime/、~/.scwiki-lima/ 的本任务资产，记录 validation.md。

## 最终阶段

- [x] T006 更新 README.md、docs/local-dev.md 和 docs/overview/ 原生开发说明，运行回归、审查暂存范围并自动提交，回写 Issue #117。

## 依赖与覆盖

严格按 T001→T002→T003→T004→T005→T006 执行，备份导出可提前进行。US1 对应 FR-001/002/003、SC-001；US2 对应 FR-004、SC-002；US3 对应 FR-005、SC-003；T006 对应 FR-006、SC-004。测试任务包含真实运行验证，不只依赖 mock。无并行代理。

## 收尾证据

真实冻结包已在独立目录完整恢复；旧 Lima 及临时验证副本已删除，原生 11 个服务运行正常。实现提交 765b05d、竞态修复 b437dbc；验证细节见 [validation.md](validation.md)。GitHub Issue 暂保留开放，代码尚未推送，远端 Spec 链接待发布后可审阅。
