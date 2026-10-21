# SC-Wiki 三组生产部署

网站、数据、解析分别由 `compose.app.yaml`、`compose.data.yaml`、`compose.compute.yaml` 管理；共享运行定义位于 `compose.runtime.yaml`。旧 `compose.yaml` 已停止提供聚合服务，避免新建另一套空数据库。本机原生开发流程不变。

## 首次准备

安装 Docker Engine 和 Compose。把本次发布源码放在服务器，复制 `release.env.example` 到 `/opt/scwiki/release.env`，填写实际源码 SHA、各镜像 digest；离线导入时可使用已核验的 `sha256:<image-config-id>`，同时保留来源 manifest digest 和归档校验清单。

私有配置位于 `/opt/scwiki/private/`：
- `app.env`：两语言数据库 URL 指向同一库、带认证 Redis、Qdrant、Neo4j、S3、JWT、SMTP 和模型目录。
- `neo4j.env`：`NEO4J_AUTH=neo4j/实际密码`。
- `qdrant.env`：`QDRANT__SERVICE__API_KEY=实际密钥`。
- `redis.conf`：监听容器内部端口、启用 AOF、配置 requirepass。
- `garage.toml`：固定本机节点配置，元数据和对象路径分别为 /var/lib/garage/meta、/var/lib/garage/data，S3 端口 3900。节点布局、私有桶及读写账号显式初始化。

私有目录权限 0700，配置文件 0600。不要把本机 `.env` 直接复制作为生产配置，其中的回环地址和本机路径不适用。不运行包含秘密展开结果的 `compose config`；入口 `config` 仅验证而不输出值。

## 命令

以下在发布源码根目录运行，必须先填写并核实发布配置：

```bash
python3 "scripts/deploy.py" --release "/opt/scwiki/release.env" init
python3 "scripts/deploy.py" --release "/opt/scwiki/release.env" config
python3 "scripts/deploy.py" --release "/opt/scwiki/release.env" pull
python3 "scripts/deploy.py" --release "/opt/scwiki/release.env" up --group data
```

数据恢复前不启动应用或 Worker。数据组初始化不代表业务恢复完成；Garage 布局、桶和账号也须先准备。

```bash
python3 "scripts/deploy.py" --release "/opt/scwiki/release.env" check
python3 "scripts/deploy.py" --release "/opt/scwiki/release.env" migrate
# 只有确实需要且备份已就绪时，显式添加 --apply 执行受保护迁移。
python3 "scripts/deploy.py" --release "/opt/scwiki/release.env" up --group compute
python3 "scripts/deploy.py" --release "/opt/scwiki/release.env" up --group app
python3 "scripts/deploy.py" --release "/opt/scwiki/release.env" status
python3 "scripts/deploy.py" --release "/opt/scwiki/release.env" logs --group compute --service worker
```

`stop --group compute` 只停止解析；`up --group app` 只更新网站。没有 `down -v`、prune 或自动删除源数据入口。普通 up 核验配置、存储身份、真实连接及 schema，不自动改库。

## 备份与恢复

先暂停新增写入和调度，排空任务，再冻结写入进程。使用 MySQL 逻辑导出、Neo4j 离线 dump、Qdrant 集合快照和别名清单，不直接复制运行中的数据库裸目录。

`scripts/production_backup.py` 提供 `objects-export/objects-restore/objects-verify`、`redis-export/redis-restore`、`mysql-inventory`。源端可通过 `--env-file` 私下加载配置；容器里使用已注入的环境。对象内容与原始键、Content-Type、sha256 等元数据一起保存，恢复要求空桶并逐项完整回读。Redis 只恢复业务任务/草稿及映射缓存，保留原过期时间，不搬旧队列执行载荷、锁、验证码和临时模型密钥。

MySQL 清单包括表结构、数量与行内容摘要；备份与恢复后分别生成并比较。源文件路径转换只能针对登记的文件字段，不能全库字符串替换。私有完整原备份另行保留。

MySQL 原生 JSON 文本导入可能使极小浮点数移动一个 double 的末位。冻结窗口须同时执行
`mysql-json-export` 保存 JSON 原文，恢复 SQL 后用 `mysql-json-restore` 核对：
只允许相邻 double 的解析误差，通过 SQL DOUBLE 转换恢复原始数值，其他类型、结构或内容变化
直接拒绝；所有修复在同一事务内，修复后必须与原文完全相等。最后仍要求整库内容摘要一致，
不能用容差替代完整性验收。JSON 补充文件须纳入同一备份摘要清单。

归档通过 SSH/rsync 传输并核对 SHA-256。先在隔离目标恢复演练，再做最终冻结迁移；服务器开放写入后回退前先保护新增数据。

## 上线边界

Caddy 公开 80/443 并管理证书；前端与数据库均通过内部网络连接。实际域名访问、登录、文件权限、解析、审核、检索、RAG、社区及资讯仍须逐项验收。/health 仅表示进程存活，/readyz 表示当前角色依赖可用。

未来将各组迁往独立机器时，分别初始化所需组、配置私网端点，并按 #132 执行数据迁移。独立 bridge 不会跨主机，私网端口覆写和来源规则须另行落实。真实多机和 #133 完整故障恢复不由单机测试替代。

当前实际状态、备份位置与验证证据见 [#146 验证记录](../../docs/specs/146-aliyun-production-deployment/validation.md)。
