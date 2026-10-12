# 使用与验收：三组独立编排

**Issue**：[ #132](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/132)。新增命令与文件尚未实现；以下操作是未来隔离验收步骤，不是已执行证据。

## 前置条件

#131 已实现，准备固定 release、私密 env、隔离存储和一台/两台 Linux Docker 测试机器。Compose v2.24+，云私网可达；真实数据组迁移必须先明确备份、空目标和维护窗口。单机容器模拟不能代替两机网络验收。

## 命令检查

```bash
python -m pytest "tests/02_maintenance_and_verification/test_deploy_cli.py" "tests/02_maintenance_and_verification/test_three_tier_compose.py" "tests/02_maintenance_and_verification/test_remote_dependencies.py" "tests/02_maintenance_and_verification/test_data_group_migration.py"
python3 "scripts/deploy.py" plan --topology single --groups all --env-file "/secure/scwiki.env" --release "/secure/release.json"
```

`/secure/` 是验收环境准备的私密路径，不应复制真实凭据到文档。plan 应只输出脱敏拓扑和前置检查，不创建容器或改数据。按部署契约显式初始化空数据、迁移 schema 后，才执行 up。

## 验收矩阵

| 场景 | 通过信号 | 来源 |
| --- | --- | --- |
| 单机首次部署 | 三项目齐备；各组连接认证成功、对象探针存在、schema 匹配 | US1、SC-001 |
| 独立生命周期 | app 更新和 compute stop 前后，data 容器 id、卷映射及样本摘要不变 | FR-002 |
| 三种配置 | Compose config 可解析；组归属正确，无跨项目 depends_on；跨机不引用另一主机 Docker 名称 | SC-002 |
| 错误依赖 | 认证/地址错误在总期限内非零退出，输出服务与错误码，无口令 | US3、SC-003 |
| schema | 已知兼容只读通过；未知版本拒绝，运行前后 schema 无变化 | FR-007 |
| 私网 | 外部测试主机无法访问数据端口；授权 app/compute 可达；管理端口不公开 | FR-005、SC-005 |
| 旧存储接管 | 从实际卷名与目录接管；错误名称拒绝，未创建同名空卷代替旧库 | FR-008 |
| 两机迁移 | 按迁移契约完整恢复、校验、切换及开放写入前回退，所有数据类别有证据 | US2、SC-004 |
| 原生兼容 | Linux/macOS 本地相关测试及隔离启动通过，无生产配置污染 | FR-010 |

## 业务冒烟与记录

登录、论文检索、原始附件、头像、RAG 数据访问、资讯任务、上传与审核至少各完成一个真实持久化场景。LLM/SMTP 外部未配置时记录未验收项，不能把基础依赖就绪写成这些能力通过。

记录实际 release/digest、引擎版本、schema 集合、源目标身份、数据核验、故障日志、实际维护时长。计划完成后不勾选实施 Tasks；运行完成后再建立 `validation.md`。
