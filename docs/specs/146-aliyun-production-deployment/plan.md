# 实施计划：单机上线

**Issue**：[ #146](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/146)
**输入**：[Spec](spec.md)、[研究](research.md)、[任务](tasks.md)

## 技术上下文

Ubuntu 24.04 amd64，4 核约 16 GB，Docker Compose；Go/Python/React 继续复用现有镜像。数据库与 Garage 先核实实际源端版本，迁移不同时升级引擎。现有源使用原生进程和 S3。
验证采用 pytest、Go 测试、Compose 配置、真实 Docker/数据库/对象服务、外网 HTTP 和业务请求。单任务解析作为首次资源约束。

## 设计与路径

三组唯一配置在 docker/compose.app.yaml、docker/compose.data.yaml、docker/compose.compute.yaml；scripts/deploy.py 管理显式项目和共享网络。现有 docker/compose.yaml 退役为明确迁移提示，不保留第二份活跃全栈定义。
backend/scripts/check_dependencies.py 和 Go readyz 提供只读就绪；Qdrant 客户端共用连接配置，Go 支持 Redis URL 认证。生产启动不依赖 migrate 容器成功才反复运行迁移。
迁移工具只导出/恢复有清单的私有目录，凭据另存；Caddy 和模型缓存持久化。

## 质量门

| 来源 | 要求 | 实现 |
|---|---|---|
| 仓库 | mayuan、按范围提交、push 单独授权 | 每次写入/提交前核对，显式暂存 |
| FR-002 | 生命周期独立 | 三个项目，数据存储 external |
| FR-003/004 | 文件与数据完整 | S3 全回读、清单、空目标恢复 |
| FR-005 | 启停不改库 | 显式迁移，schema 只读检查 |
| FR-007 | 秘密边界 | 私有 env、脱敏状态、备份不导出短期凭据 |

## 需求映射与阶段

| 需求/成功标准 | 组件 | 任务与验证 |
|---|---|---|
| FR-001 / SC-001 | Caddy、入口、DNS | T003、T007 |
| FR-002/005 / SC-003/005 | 三组编排、部署命令、就绪 | T002、T003、T006、T007 |
| FR-003/004/007 / SC-002 | 对象/数据库备份恢复 | T004、T005、T006 |
| FR-006 / SC-004 | 真实业务与文档 | T007、T008 |

先建立全部文档与配置验证，再实施连接和编排，准备服务器及恢复演练，最后进入冻结迁移与正式验收。#132 同机部分以本次实现证据回写，跨机不勾选。

## Embedding 接入补充

FR-008 / SC-004 → 用户选定的百炼 text-embedding-v4 → backend/ingest/embedder.py 与 RagSettings → T009。
通过私有配置指定 1536 维，与现有 Qdrant 集合匹配，不删除或重建业务集合。统一入口按每批最多 10 段调用，按响应 index 对齐文本，校验数量、维度和有限数值后再允许索引。
验证覆盖多批请求、异常响应拒绝、真实供应商调用和服务器临时测试集合写入/查询/清理；业务审核过滤不因验收而放宽。
发布使用已验证提交的 Docker Hub 制品；私有配置仅同步 Embedding 项，保留线上数据库与其他凭据。
