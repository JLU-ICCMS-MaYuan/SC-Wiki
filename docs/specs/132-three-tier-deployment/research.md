# 研究与决策：三组服务独立编排

**Issue**：[ #132](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/132)，2026-10-12。仅基于仓库静态核查。

## 现状证据

| 位置 | 已核查事实 |
| --- | --- |
| `docker/compose.yaml` | 各组在一个项目；Go Redis、Python Redis/Qdrant/Neo4j/GROBID 地址写死；API/Worker 依赖 migrate |
| 同一文件的数据服务 | MySQL/Neo4j/Qdrant 有未限定主机接口的端口映射；Redis AOF 持久化；Qdrant 使用可变 latest 标签 |
| `goserver/cache/cache.go` | 仅配置地址，无 Redis 认证参数；客户端自动初始化 |
| `backend/rag/vectordb.py`、`service.py`、`backend/scripts/build_summary_index.py` | 多个 Qdrant 客户端入口未统一认证配置 |
| `backend/scripts/run_migrations.py` | 含导入库基线 stamp 和 Issue90 安全目标；不能直接替换为任意 head |
| `goserver/main.go`、`backend/main.py` | 存活健康接口不等于全部数据依赖可用 |
| `scripts/dev.sh`、`scripts/local_deploy/` | 本地安装、端口与 schema 流程独立，不能拿来管理生产远程实例 |

## D1：三个 Compose 项目，由薄编排命令组合

使用 `docker/compose.app.yaml`、`compose.data.yaml`、`compose.compute.yaml` 和 `scripts/deploy.py`。同机组合命令依次调用三个项目，仍然保留独立生命周期；不使用一个聚合 Compose 把三个组重新合为同一项目。项目名固定为 `<deployment-id>-app/data/compute`。

同机创建显式共享 Docker bridge；不同主机各自拥有本地 bridge，通过配置的私网端点跨主机。跨组不使用 `depends_on`；同组 Nginx→Go、Worker→GROBID 可保留依赖。云安全组由管理员按矩阵配置，工具只检查和报告。

旧 `docker/compose.yaml` 作为旧部署入口在新发布中退役，文档明确改用部署命令，不能让旧命令悄悄启动另一套全栈。先完成实际卷/目录接管，再移除旧入口；旧发布与原数据仍可用于维护窗口回退。新版本不维护第二套聚合定义。

## D2：对象服务首版默认单节点 MinIO，客户端不绑定实现

MinIO 仅作为初期同机自托管的 S3 实现，使用私有 bucket 与独立运行访问账号。管理账号只用于显式初始化；管理端口不发布到公网。版本必须固定到验收通过的镜像 digest，不使用 latest；实现阶段从实际可取得、经许可证和兼容性核验的发行版解析 digest 并写发布清单，文档不编造尚未核验的版本值。

应用契约仅使用 #131 的标准 S3 操作。后续换云对象存储是另一次有校验的数据迁移，不承诺只改 endpoint 就自动转移已有对象。服务品牌替换须补相同 S3 行为验收，不修改业务 API。

## D3：认证、连接与就绪集中配置

Go 优先 `REDIS_URL`，未设置时保留本地 `REDIS_ADDR`；Python 与资讯服务沿用 `REDIS_URL`。Qdrant 新增共用客户端工厂，统一 URL、API key 与超时，覆盖业务与运维入口。MySQL 保留两语言 DSN 转换并核验同步/异步 URL 指向同一库；Neo4j 沿用 URI/账号密码。

启动前检查所有必需依赖，但运行时就绪按角色分解：Go 检查 MySQL/Redis/头像存储，Python 检查其数据库/Redis/文件及 RAG 依赖，计算组检查 MySQL/Redis/文件/GROBID。`/health` 继续表示存活，内部 `/readyz` 表示对应角色就绪，不承诺解析或 LLM 科学结果成功。运行中只影响依赖它的功能，不因 GROBID 故障阻断网站登录。

## D4：显式 schema 操作与存储身份

发布清单记录应用 digest、契约版本、引擎 digest、所需 Alembic revision 集合。启动只读核验；`migrate-schema` 使用短生命周期维护容器及独立迁移凭据，默认只显示计划，`--apply` 才执行。保留现有 Issue90 确认约束与多 head 处理，不自动 stamp 未知数据库。

旧命名卷从 `docker inspect` 获取实际名称并显式作为 external 卷引用；绑定目录使用规范绝对路径。新部署以显式 `init-data` 初始化，普通 up 不创建未知持久存储。部署身份、目录和卷不一致即阻断。

## D5：停写备份恢复，不复制运行中的数据裸目录

数据迁移复用 #131 的文件完整性清单，按引擎支持的逻辑导出/快照方式处理其余数据。Redis 明确区分业务草稿与瞬态队列/密钥。目标只允许空数据命名空间；迁移期间固定引擎版本，不顺便升级。用户允许维护窗口，因此不引入增量复制与双写。
