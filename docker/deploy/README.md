# SC-Wiki 三组生产部署

主目录迁移目标为 `/home/mayuan/sc-wiki`（发布与私有配置）和
`/home/mayuan/scwiki-containered`（本项目持久数据）。实际切换与核验状态见
[#146 验证记录](../../docs/specs/146-aliyun-production-deployment/validation.md)。
下文 `/opt/scwiki` 的初始部署示例适用于旧布局；新布局操作使用文末的当前实例命令。

网站、数据、解析分别由 `compose.app.yaml`、`compose.data.yaml`、`compose.compute.yaml` 管理；共享运行定义位于 `compose.runtime.yaml`。旧 `compose.yaml` 已停止提供聚合服务，避免新建另一套空数据库。本机原生开发流程不变。

## 首次准备

阿里云只从 `origin/remote` 的固定提交发布，本地开发继续使用 `mayuan`。先验证并合并代码到
`remote`，记录完整 SHA，再构建和部署；推送不会自动更新服务器。镜像构建工作流只允许从
`remote` 手动触发，手动运行会向 Docker Hub 发布 `remote` 与 `sha-<短提交>` 标签；普通 Git
推送不发布镜像。默认部署 Actions 构建的原版镜像，实际运行固定 digest；网络受限时转运同一镜像，
核对来源 digest、配置与文件层后记录实际本地镜像 ID。仅在用户另行明确要求时才使用服务器手动构建。
手动运行镜像工作流时按目标选择 `platforms`：当前阿里云 x86_64 使用默认 `linux/amd64`；
倚天等 ARM 服务器选择 `linux/arm64`，同时交付两种架构时选择多架构选项。
发布清单同时记录 `SOURCE_BRANCH=remote` 和实际 `SOURCE_COMMIT`；不能只修改版本记录而不更新程序。
表单约束工作流在 `remote` 推送后执行。Git 推送、Docker Hub 镜像推送和线上切换分别按本次授权执行。

从归档构建前端时，公开静态目录须可由 Nginx 读取（目录 0755、文件 0644）；只核对文件摘要
不能发现目录访问权限问题。发布前检查实际 JS 响应类型与浏览器渲染。Docker 挂载清单按
目标路径排序后逐字段比较，顺序变化不算实际挂载变化；这些检查不能用于放宽数据卷或私有配置权限。

Compose 至少使用 2.30，以支持 `env_file.format: raw`。私有 env 使用不带外层引号的
`KEY=value` 行；Compose 与维护容器均按原值读取，密码中的美元符号和引号不会再次展开。

安装 Docker Engine 和 Compose。把本次发布源码放在服务器，复制 `release.env.example` 到 `/opt/scwiki/release.env`，填写实际源码 SHA、各镜像 digest；离线导入时使用核验后的实际本地镜像 ID，同时保留来源 manifest digest 和归档校验清单。Docker 29 的本地镜像 ID 可能不同于配置 JSON 的 SHA-256，不能混用。

私有配置位于 `/opt/scwiki/private/`：
- `app.env`：两语言数据库 URL 指向同一库、带认证 Redis、Qdrant、Neo4j、S3、JWT、SMTP 和模型目录。
- `neo4j.env`：`NEO4J_AUTH=neo4j/实际密码`。
- `qdrant.env`：`QDRANT__SERVICE__API_KEY=实际密钥`。
- `redis.conf`：监听容器内部端口、启用 AOF、配置 requirepass。
- `garage.toml`：固定本机节点配置，元数据和对象路径分别为 /var/lib/garage/meta、/var/lib/garage/data，S3 端口 3900。节点布局、私有桶及读写账号显式初始化。

私有目录权限 0700，配置文件 0600。不要把本机 `.env` 直接复制作为生产配置，其中的回环地址和本机路径不适用。不运行包含秘密展开结果的 `compose config`；入口 `config` 仅验证而不输出值。

解析模型缓存统一位于计算组 `/models` 卷：Hugging Face、Datalab 和 MinerU 分别使用
`/models/huggingface`、`/models/cache`、`/models/mineru`。这是可重建缓存，不是业务文件，
不能代替 Garage 对象备份。已有模型权重可在摘要核验后复制以避免重复下载。

## 命令

### 独立 Embedding 配置

在私有 `app.env` 配置 `EMBEDDING_API_KEY`、`EMBEDDING_BASE_URL`、
`EMBEDDING_MODEL=text-embedding-v4`、`EMBEDDING_DIMENSIONS=1536`、
`EMBEDDING_BATCH_SIZE=10`。Base URL 使用密钥对应地域的 OpenAI 兼容根地址，
不含末尾 `/embeddings`。这组配置与聊天模型目录独立。

1536 是当前实例既有集合的维度；其他部署须先核对集合配置。未设置维度时采用模型默认值，
不能把不同模型或维度的向量混入旧索引。分批默认每批 10 段，全部成功后才写入本次索引。
更新配置后重新创建网站组及计算组的 Python 容器；单纯 restart 不会刷新容器环境变量。
仅生成向量和查询会产生供应商用量，重复读取已有向量不重新调用 Embedding。

### 部署命令

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

Caddy 将 API 直接转发给 Go，并用实际连接来源覆盖 X-Real-IP；Go 的
`TRUSTED_PROXIES` 只配置受控 Docker 网络 CIDR。静态页面交给 Nginx。
不要信任公网传入的代理头；上传请求保留 51 MiB 请求体上限。

未来将各组迁往独立机器时，分别初始化所需组、配置私网端点，并按 #132 执行数据迁移。独立 bridge 不会跨主机，私网端口覆写和来源规则须另行落实。真实多机和 #133 完整故障恢复不由单机测试替代。

当前实际状态、备份位置与验证证据见 [#146 验证记录](../../docs/specs/146-aliyun-production-deployment/validation.md)。

## 当前实例

### 网络受限时的同版本镜像差分

服务器保留了上一版本的完整 `image.tar.gz` 时，可以使用
`.github/workflows/export-deployment-delta.yml` 生成 VCDIFF 包。该工作流只允许从 `remote` 手动运行，
必须输入仍可下载的基准/目标运行 ID、制品 ID 和目标源码完整 SHA，并检查该提交属于发布分支。
完整镜像导出也只允许从 `remote` 手动运行，必须显式填写本次镜像引用 JSON；不再自动使用历史清单。
导出端验证完整压缩归档摘要，实际还原并比较目标 tar 的 SHA-256。

服务器需要 `xdelta3`，使用 `scripts/deployment_image_delta.py restore`，分别通过
`--base-archive` 指定保留的原压缩包、`--package` 指定包含 manifest.json、source.json 和
image.vcdiff 的目录、`--output` 指定尚不存在的新 tar 文件。工具验证基准与差分摘要，
还原后要求完整目标 tar 摘要完全一致；失败时禁止导入，不覆盖旧文件。
还须核验差分制品自身的 GitHub artifact 摘要，再执行 `docker load`，并比较导入镜像的
配置、文件层和平台与 source.json 一致，最后记录实际本地镜像 ID。此流程不改目标镜像版本。

### 连接与维护

网站为 https://www.sc-wiki.com，服务器为 `47.111.123.225`。用户指定迁移后的发布入口为
`/home/mayuan/sc-wiki/current`，发布清单为 `/home/mayuan/sc-wiki/release.env`，
私有配置位于 `/home/mayuan/sc-wiki/private/`。首次备份保留在新发布根的
`backups/initial-20261021/`，本次迁移证据位于 `backups/relocation-20261022/`。

```bash
# 登录 mayuan 后在服务器执行，Docker 管理使用 sudo。
cd "/home/mayuan/sc-wiki/current"
sudo python3 "scripts/deploy.py" --release "/home/mayuan/sc-wiki/release.env" status
sudo python3 "scripts/deploy.py" --release "/home/mayuan/sc-wiki/release.env" logs --group compute --service worker
```

`SCWIKI_VOLUME_ROOT=/home/mayuan/scwiki-containered`、`SCWIKI_VOLUME_PREFIX=scwiki-home`
将 13 个活跃卷绑定到该数据根的同名子目录，三个 Compose 项目和网络名称仍为 scwiki。
发布根归 mayuan 管理；数据根可由 mayuan 查看目录列表，但 MySQL、Redis、Neo4j 等子目录
保留服务原有 UID/GID 和权限，禁止递归 chown/chmod。历史演练数据库保存于数据根的
`archive/rehearsal-mysql`，不是线上活跃数据。

日常操作只使用新入口。2026-10-22 按用户要求删除旧 `/opt/scwiki`、迁移临时目录和已停止的
`scwiki-rehearsal-mysql` 容器。原 `scwiki_*` 数据卷和镜像仍保留，不再承接新写入；
迁移工作区、旧配置和容器信息归档于新发布根的 `backups/cleanup-opt-20261022/`。
回退前先暂停入口和任务，保存新目录中的新增业务数据，再从保留记录制定恢复步骤；
不要执行已不存在的旧入口，也禁止直接用旧卷覆盖当前业务。Docker `/var/lib/docker` 与 containerd
`/var/lib/containerd` 保持不变。目录迁移后的启动会严格核验部署标记与卷实际 device 路径，
缺失目录时不会静默创建空数据。

本地源数据及私有独立备份继续保留。Embedding 与尚未完成的业务验收以 #146 为准；
不要因为网站已可访问而关闭所有部署验收任务。

2026-10-21 20:25 复查时公网域名已被阿里云 `Non-compliance ICP Filing` 页面拦截，
HTTPS 握手被重置；服务器内应用正常。需要处理备案/接入状态后再验收公网可用性，
此前成功的 HTTP 和浏览器测试不能代表当前外网状态。
