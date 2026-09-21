# 实施任务：本地 Neo4j 端口调整

**输入**：[Spec](spec.md)、[Plan](plan.md)、[Research](research.md)、[Quickstart](quickstart.md)

本文件补录已执行的技术任务；Issue 状态由 [#113](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/113) 管理。

## 阶段 1：准备

- [x] T001 将 `.local/log/neo4j.log`、Windows 占用与 WSL 网络模式的调查结果记录到 `docs/specs/113-local-neo4j-port/research.md`，确认直接原因与修复边界。（FR-005）

## 阶段 2：US1 恢复本地连接

- [x] T002 [US1] 在 `scripts/lib-local.sh`、`scripts/setup-local.sh`、`scripts/gen-env.py` 同步 17687；更新本机 `.env` 和 `.local/neo4j/conf/neo4j.conf`，保留凭据与数据。（FR-001～FR-004；提交 `7a614bb3`）
- [x] T003 [US1] 执行 `scripts/dev.sh start neo4j` 并使用真实驱动验证认证、`RETURN 1` 和 HTTP 公布地址；证据写入 `docs/specs/113-local-neo4j-port/quickstart.md`。（FR-001、FR-002、FR-004；SC-001、SC-002）

**独立验收**：真实启动后可使用现有凭据连接 17687，管理入口公布相同地址。

## 阶段 3：US2 保持配置与说明一致

- [x] T004 [US2] 核验 `scripts/gen-env.py` 的旧地址改写和缺失项默认值，并核对 `scripts/local_deploy/config.py`、`scripts/local_deploy/environment.py` 的端口同步；后两文件保留 #112 未提交状态。（FR-003、FR-005；SC-002、SC-003）
- [x] T005 [US2] 补齐 `docs/specs/113-local-neo4j-port/`，更新 `README.md` 与 `docs/overview/02_Decentralized_Maintenance_and_Verification/deployment-and-runtime.md`，验证 Issue 链接及需求覆盖。（FR-005；SC-003）

**独立验收**：生成地址与运行地址一致，文档区分本 Bug、#112 和完整服务验收范围。

## 依赖与证据边界

T001 → T002 → T003 → T004 → T005，串行完成。本轮补录不重新实现 T002。
T003 的启动证据来自同日已完成操作，认证查询和公布地址在文档补录时再次验证通过。
T004 仅核验 #112 配置约定；不代表 #112 代码已提交或跨机器部署已验收。
