# 部署命令与连接契约

**来源**：[Spec](../spec.md) FR-001～FR-008、FR-010～FR-012。以下命令接口尚未实现。

## 命令

```text
python3 scripts/deploy.py plan --topology single --groups all --env-file PATH --release PATH
python3 scripts/deploy.py init-data --topology single --groups data --env-file PATH --release PATH --apply
python3 scripts/deploy.py up --topology single --groups all --env-file PATH --release PATH
python3 scripts/deploy.py stop --topology dual --groups app,compute --env-file PATH --release PATH
python3 scripts/deploy.py status --topology triple --groups app --env-file PATH --release PATH
python3 scripts/deploy.py check --topology triple --groups compute --env-file PATH --release PATH
python3 scripts/deploy.py migrate-schema --topology single --groups data --env-file PATH --release PATH
```

- `topology` 为 single/dual/triple，groups 为 app/data/compute 的集合；`all` 只允许 single。本命令只控制本机选定组，不通过 SSH 操作其他机器。
- dual 的 A 允许 app/compute，B 允许 data；triple 每台只运行对应组。实例配置登记角色，选择不符即拒绝。单机 up all 依次启动 data、compute、app，仍为三个 Compose 项目。
- `plan/status/check` 不改业务数据；`plan` 也不创建目录、网络、容器。`init-data --apply` 是唯一新存储初始化入口，非空未知目标拒绝；旧存储使用明确身份映射接管，不执行 init-data。
- 新部署先初始化数据、运行显式 schema 迁移及 #131 必要文件迁移，再 up 业务组。迁移命令默认只打印目标差异，`--apply` 执行；未知基线、多 head 歧义和缺少既有确认均阻断。
- `stop` 只停止选定组，不删除卷和共享网络；首版不提供 down -v、prune 或源数据清理包装命令。更换镜像版本使用 up 重建选定组，restart 不作为更新版本的方法。
- 退出码：0 成功、2 配置/角色/版本错误、3 连接或就绪失败、4 数据身份或完整性错误。报告包含组、服务、阶段、耗时及错误码，不包含凭据。

## 环境配置

复用 `DATABASE_URL`、`RAG_DATABASE_URL`、`NEO4J_URI/USER/PASSWORD`、`GROBID_URL` 及 #131 的文件配置。`RAG_DATABASE_URL` 省略则由 DATABASE_URL 转异步驱动；显式配置时须核验同主机、端口和数据库。

`REDIS_URL` 是三组共用主入口，支持账号/密码与数据库编号；Go 本地未设置 URL 才回退 `REDIS_ADDR`。生产拒绝依赖地址默认值。Qdrant 采用 `QDRANT_URL`、`QDRANT_API_KEY`；未提供 URL 时保留本地 `QDRANT_HOST/PORT`，生产必须显式配置。所有客户端及健康/索引脚本使用同一工厂。

同机 data/compute 的跨组别名分别为 mysql、redis、neo4j、qdrant、object-storage、grobid；跨机由环境文件改为私网 DNS/IP。API 与 Worker 的 JWT 和任务契约版本必须一致，模型配置通过既有短期任务配置传递，不写入命令行或备份。

## 网络矩阵

| 接收端 | 允许来源 | 首版端口 |
| --- | --- | --- |
| Nginx | 用户入口 | HTTP 80；HTTPS 沿用部署的外部 TLS 入口 |
| MySQL | app、compute、维护节点 | 3306 |
| Redis | app、compute、维护节点 | 6379 |
| Neo4j Bolt | 需要图功能的 app/compute、维护节点 | 7687 |
| Qdrant HTTP | app、compute、维护节点 | 6333；默认不启用 gRPC |
| S3 | app、compute、维护节点 | 9000（默认自托管实现） |
| GROBID | compute 与调用它的 app | 8070 |

同机不映射数据端口；跨机覆写文件要求明确私网绑定 IP，禁止使用默认 0.0.0.0。Neo4j 浏览器、S3 控制台只通过维护通道访问。Docker bridge 不能跨主机；每台机器独立网络，跨组流量走私网端口。云安全组与宿主规则需实际验证，不能仅凭 Compose bind 声称来源限制生效。

## 就绪与超时

启动检查每次网络调用最长 5 秒，总等待默认 120 秒，间隔 2 秒；总期限可配置但必须有限。检查认证 MySQL SELECT/schema、Redis PING、Qdrant 集合读取、Neo4j RETURN 1、S3 bucket/已初始化探针对象以及需要时的 GROBID isalive。

`/health` 保留存活语义；Go/Python 增加内部 `/readyz`，200 为角色依赖就绪、503 为未就绪。返回依赖名称与稳定码，不返回端点和凭据；Nginx 不将内部就绪诊断公开。Worker 用命令检查数据依赖与心跳，不将其等同为任务成功。初始化探针对象由 init-data 创建，就绪检查不向业务存储写探针。
