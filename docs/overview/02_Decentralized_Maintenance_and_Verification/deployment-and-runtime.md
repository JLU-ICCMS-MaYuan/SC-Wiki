# 部署与运行时

## 功能说明

说明 SC-Wiki 的生产 Docker 部署与本地开发运行时两条链路：服务组成、配置入口、数据挂载和启动边界。本文不替代部署包中的数据导入操作说明。

镜像积累原因、只读占用快照、清理边界和服务器开发建议见[部署技术分析](../00_deploy_technical/docker-storage-and-development.md)。

## 当前行为

### 生产：Docker Compose

- 生产编排文件为 `docker/compose.yaml`，包含 frontend、goserver、python、migrate、worker、news-worker、news-scheduler、mysql、redis、neo4j、qdrant 和 grobid 共 12 个服务，使用 8 类镜像；Python API、迁移和三个后台任务服务共用 Python 镜像。GROBID 通过 `/api/isalive` 健康检查后才允许 Python/Worker 启动，应用启动还受迁移任务成功完成的约束。
- frontend 使用 Nginx 提供前端静态资源并反向代理；Go 服务提供主要公开 API；未匹配的 Python 能力通过 Go 转发到 Python 服务。
- Go 服务挂载 `graph.json`、`clean_results` 和持久化头像目录 `/data/avatars`；Python/Worker 服务挂载上传文件、富化结果和属性映射缓存，并通过 `GROBID_URL=http://grobid:8070` 调用引用解析服务。
- MySQL、Redis、Neo4j 使用命名卷，Qdrant 使用宿主机数据目录持久化；当前 GROBID 未配置持久化挂载。服务通过 healthcheck 和 `depends_on` 控制启动顺序。
- 当前仓库只包含 `docker/compose.yaml`；源码构建可分别使用 `docker/*.Dockerfile`，不存在 `docker/compose.dev.yaml`。

### 本地开发：宿主机进程（[Issue #71](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/71)）

- 本地服务全部运行在宿主机，由 `scripts/dev.sh` 编排，入口为 `Makefile`（`make start` / `stop` / `status` / `logs`）。GROBID 0.8.1 从官方源码、默认 Wapiti 模型及原生库构建，使用 `.local/grobid-java` 中独立 Java 17，API 8070 和管理接口 8071 均绑定回环地址；本地安装与启停不调用 Docker。
- 请求链路为浏览器 → Vite 5173 →（`/api` 代理）→ goserver 8080 →（未匹配路由反代）→ uvicorn 8000。两段代理均为既有实现，本地化未修改 `backend/` 与 `goserver/` 源码。
- 前端 Vite HMR、Python `uvicorn --reload`、goserver 文件监听重编译和上传 Worker 的 `watchfiles` 包装支持代码变更重载。Go 编译失败时保留旧进程继续服务。资讯 Worker 和 Scheduler 无热重载包装，修改代码后须重启相应进程。
- 四个存储服务来自本机安装而非容器：MySQL 8.4.2、Redis 8.10.1 与 Neo4j 所需的 OpenJDK 21 均来自 conda 环境 `sc-wiki`；Neo4j 5.26.29 使用官方发行归档，和 Qdrant 1.19.0 一样安装在 `.local/`。应用 Python 依赖也使用 `sc-wiki`。
- MySQL 监听 3307 而非 3306：宿主机 3306 已被与本项目无关的系统级 MySQL 占用。
- 本地 Neo4j 的 Bolt 连接使用 `127.0.0.1:17687`，HTTP 管理入口保持 `127.0.0.1:7474`；客户端连接地址、监听地址与公布地址一致。该约定避开本机曾发生的 Windows 向日葵占用 7687 问题，不改变 Docker 生产端口。
- 全部数据存放于仓库内 `.data/`（四个数据库的数据目录、上传文件、解析产物、头像），运行时产物在 `.local/`（二进制、MySQL 配置、pid、日志）。两者均已 gitignore。
- `make start` 默认启动 `news-worker` 与 `news-scheduler`；两者分别消费资讯队列和检查资讯日程，Worker 在 Redis 连接异常后重建连接继续运行。
- 测试可在宿主机直接运行（`scripts/run-tests.sh`，含 backend / go / frontend 三目标），不再需要挂载仓库的一次性容器。
- 使用说明与实施过程中的环境约束记录见 `docs/local-dev.md`。

## 工作流程

### 生产部署

1. 准备 Compose 读取的 `.env`，填写数据库、JWT、Neo4j、LLM、Embedding 和 SMTP 配置；SMTP 需要主机、端口、发件人、账号、授权码和 TLS 模式；网易示例使用 smtp.163.com:465、implicit TLS 与 sc_wiki@163.com。
2. 准备 `data/` 下的图谱快照、外部数据、上传目录、富化结果和 Qdrant 存储。
3. 使用 `docker compose -f docker/compose.yaml up -d` 启动服务；首次部署的数据导入和 Neo4j dump 恢复遵循 `docker/deploy/README.md`。
4. 通过 frontend 入口访问站点；Go 的 `/health` 和 Python/RAG 健康接口用于分别核验服务状态。

### 本地开发

1. 用户先准备 Conda 和系统基础工具；`make deploy` 寻找其实际前缀并复用兼容的 `sc-wiki`，环境缺失则创建。脚本不安装或升级 Conda，不修改 base；缺少/不可用 Conda 或 `sc-wiki` 实际指向 base 时在预检阶段拒绝，可用 `CONDA_EXE` 指定安装位置。依赖版本和下载摘要由 `scripts/local-deploy-versions.json` 管理；Go、Neo4j 和 Qdrant 位于 `.local/`。`make setup` 委托同一安装器，仅准备依赖和配置；完整分工见[本地开发说明](../../local-dev.md#工具和配置分工)。
2. `make deploy` 自动检查 `dist/` 的直接子项：只有一个压缩包时自动校验解压，多于一个明确要求只能保留一个，`.sha256` 不计数。显式 `BUNDLE` 可以指定来源但不绕过多包限制。压缩包与已有 `.deployment/manifest.json` 须一致；完全无包才初始化空库。有包时沿用当前源码/服务版本一致性、空目标和数据完整性检查，恢复到临时目录后提升为 `.data`。已有不属于该部署的数据（包括另一空库部署的实例）会阻断，成功后的重跑不重复导入。`make migrate` 保留为旧 Docker 卷迁移入口。
3. `make start` 启动全部服务，按依赖顺序等待健康检查。便携实例核验进程归属和真实 schema，只核验、不升级数据库；没有便携记录的旧实例保留原迁移启动路径。
4. 浏览器访问 `http://127.0.0.1:5173`。`make status` 查看各服务状态，`make logs S=<服务>` 跟踪日志。

部署前置检查不要求 Docker，阻塞报告通过 `next_steps` 提供处理建议，
并包含 `error_code=preflight_failed`、`phase=preflight`。系统或目标预检阻塞时，Conda
状态显示“未检查”，不能据此推断需要创建环境。此阶段只输出报告，不创建配置或运行数据。
Conda 自身检查失败时状态为“未就绪（Conda 预检未通过）”；只有找到可用 Conda 且没有
`sc-wiki` 时才显示“将创建 sc-wiki”。安装器保留缺失 Conda 的第二道拒绝检查，不自动引导 Miniforge。
多包、坏包、源码不兼容或包/部署记录冲突时，普通部署和只读预检均在安装前退出，
不改写现有配置、数据和部署报告。自动恢复只接受现有可校验 tar 迁移包，不是任意 ZIP
或裸 SQL 导入；自动发现成功不代表旧版本备份已恢复，当前跨源码兼容边界见
[#112](../../specs/112-portable-local-deployment/validation.md)。
Neo4j/GROBID 来源和摘要由统一版本清单固定；网络下载失败不会转用 Docker 或跳过服务。
本机 GROBID 的真实引用/PDF 解析、重复启动和停止已验证；Neo4j CDN 返回 403 时可使用
版本清单中的发行对象存储备用地址，仍验证同一个官方 SHA-256。当前 Ubuntu 26.04
机器已完成整套无 Docker 空库部署、重复部署和源码重载验证；预检通过仍不代表后续网络
安装必然成功，也不能替代其他平台或跨机器恢复验收。

Go 安装器和启动脚本共用 GOPATH/GOCACHE/GOPROXY，默认沿用项目既有模块镜像，
显式进程配置优先；不修改全局 Go 设置，保留模块校验。GROBID 单独使用 Java 17，
不会替换 Neo4j 的 Java 21。

`make frozen` 以干净 HEAD 的源码和业务数据生成迁移包。外部凭据不进入包；源端停写后
导出 MySQL、Neo4j、Qdrant 和 Redis 上传草稿，结束后恢复应用。Redis 草稿恢复会同步
落盘，便携实例正常停止也会保存。实现已进入真实隔离验证，干净 Ubuntu 22.04
和另一台机器的完整安装验收尚未完成，见 [#112 验证记录](../../specs/112-portable-local-deployment/validation.md)。

已有 Neo4j 安装切换到 17687 时，需要同步 `.env` 的 `NEO4J_URI` 与
`.local/neo4j/conf/neo4j.conf` 中的 Bolt 监听、公布地址，并让服务及客户端重新加载配置。
本次修复已直接同步现有本机配置，无需重新安装数据库。
单服务启动和只读验证见 [#113 验证说明](../../specs/113-local-neo4j-port/quickstart.md)。

### 本地改动如何进入 Docker 部署

本地开发不使用 nginx，前端入口是 Vite dev server。这不影响改动进入生产镜像 —— 两者是无关的两件事：

- `docker/frontend.Dockerfile` 先 `COPY frontend/ .` 拷入**源码**，再在镜像内执行 `npm run build`（即 `tsc -b && vite build`）。nginx 拿到的是该次构建的新产物，不持有任何代码副本，也不参与编译。
- 因此在 Vite 中改的每一行前端代码，重建镜像时都会被编译进去。只有改 `docker/nginx.conf` 本身才需要关注 nginx。
- 本地不用 nginx 的原因是它与热重载互斥：nginx 提供的是 `vite build` 的已构建产物，而热重载的前提是不构建、由 Vite 按需转译源文件。确定前端入口必须是 Vite 后，nginx 剩下的 `/api` 代理职责已由 `frontend/vite.config.ts` 承担，再叠一层即为冗余。

真实差异不是「改动没进去」，而是**同一份代码在两条链路下行为可能不同**，且方向是本地比生产宽松（风险为「本地能用、生产不能用」）：

| 差异项 | 生产 | 本地 | 说明 |
| --- | --- | --- | --- |
| `client_max_body_size` | 50M / 51M | 无上限 | 本地不会触发体积拒绝 |
| `proxy_request_buffering off` | 有 | 无 | 影响大文件上传的流式行为 |
| `proxy_set_header Accept-Encoding ""` | 有 | 无 | 影响响应压缩链路，曾致上传响应 JSON 截断 |
| `removeHeavyPreloads` 插件、`manualChunks` 分包 | 生效 | 不生效 | 仅构建期生效，dev 模式不走，故首屏预取与 chunk 划分问题本地不可见 |

上表前三项只在改动上传相关功能时才有实际意义；第四项影响首屏加载表现。当前的处置是先不引入额外机制，把这些差异作为已知观察项记录（见「已知问题」）。若日后需要收敛，两条候选路径是：新增一个只跑生产构建、不产镜像的校验命令（可覆盖类型错误、构建期插件与依赖缺失等多数「本地好使、镜像挂掉」的情形）；或把 nginx 置于 Vite 之前而非替代之，以复现上表前三项配置，代价是多一层调试面且 HMR 的 WebSocket 经代理偶有连接问题。

## 约束

- `docker/compose.yaml` 依赖预置镜像和外部数据目录，不等同于从空目录自动构建完整数据集。
- RAG 需要 Qdrant、RAG 数据库、Embedding 和 LLM 配置；主业务数据库可用不代表 RAG 可用。
- 旧 Neo4j 图谱、`graph.json` 快照和 MySQL 数据的同步时机不由 Compose 自动解决；Issue #81 的论文引用图直接由 MySQL 查询，不需要 Neo4j 同步。
- 密钥只能通过环境变量注入，文档不记录实际凭据。Go 邮件配置支持 `SMTP_HOST`、`SMTP_PORT`、`SMTP_USER`/`SMTP_USERNAME`、`SMTP_PASSWORD`、`SMTP_FROM` 和 `SMTP_TLS_MODE`。
- `AVATAR_DIR` 默认为数据目录下 `avatars`，Compose 固定为 `/data/avatars` 并挂载宿主 `docker/data/avatars`；部署备份需包含该目录。
- `docker/deploy/README.md` 中的镜像标签、归档文件和导入命令属于交付包说明，发布前需要按实际归档核验。
- 本地应用 Python、MySQL、Redis 和 OpenJDK 21 由 conda 环境 `sc-wiki` 管理；GROBID Java 17 位于项目私有前缀，不替换系统 Java 或应用环境的 Java 21。
- 本地 MySQL 客户端命令必须带 `--defaults-file`：系统 `/etc/mysql/my.cnf` 含 `user = mysql` 与指向 `/var/log/mysql/` 的错误日志路径，以普通用户启动会失败。
- 本地开发链路不含 nginx，`docker/nginx.conf` 中的 `client_max_body_size`、`proxy_request_buffering off` 与 `Accept-Encoding` 清空均不生效；`vite build` 期生效的 `removeHeavyPreloads` 与 `manualChunks` 在 dev 模式下同样不走。这不影响改动进入镜像（镜像内会重新构建源码），但同一份代码在两条链路下的上传与首屏行为可能不同，详见「本地改动如何进入 Docker 部署」。
- 当前 WSL `networkingMode=mirrored` 本地开发环境中，UFW 必须保持停止且禁止开机启动。宝塔安装器启用 UFW 并设置默认拒绝策略后，`loopback0` 上的 localhost TCP 流量会被拦截，导致 VS Code Remote WSL 和 Windows 访问本地服务失败。该约束只适用于当前 WSL 本地开发环境，不改变生产服务器的防火墙策略（[Issue #89](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/89)）。

## 代码与测试

- `docker/compose.yaml`
- `docker/nginx.conf`
- `docker/frontend.Dockerfile`
- `docker/goserver.Dockerfile`
- `docker/python.Dockerfile`
- `docker/deploy/README.md`
- `goserver/main.go`
- `backend/main.py`
- `Makefile`
- `scripts/lib-local.sh`
- `scripts/setup-local.sh`
- `scripts/local_deploy/native.py`
- `scripts/local_deploy/environment.py`
- `scripts/local_deploy/bundle.py`
- `scripts/local_deploy/cli.py`
- `tests/02_maintenance_and_verification/test_local_bundle_discovery.py`
- `scripts/dev.sh`
- `scripts/goserver-watch.sh`
- `scripts/goserver-run.sh`
- `scripts/migrate-from-docker.sh`
- `scripts/gen-env.py`
- `scripts/run-tests.sh`
- `docs/local-dev.md`

## 相关变更记录

- [Issue #71](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/71)：本地化开发环境，移除 Docker 依赖（`docs/specs/71-local-dev-no-docker/`）
- [Issue #89](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/89)：WSL mirrored 与宝塔防火墙的本地开发兼容性（[Spec](../../specs/89-local-dev-firewall-compatibility/spec.md)）
- [Issue #113](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/113)：本地 Neo4j Bolt 端口调整为 17687（[Spec](../../specs/113-local-neo4j-port/spec.md)）

## 已知问题

- 交付包中的镜像标签和数据归档是否与当前 Compose 文件一致，待发布前核验。
- 本地直接运行 Go/Python 与 Docker 反向代理链路的接口覆盖仍需按部署环境验证。
- SMTP 服务商连通性、TLS 模式和实际发件能力需要在目标环境验收。
- 本地开发的大文件上传未在缺少 nginx 的链路下验证，行为是否与生产一致待核验。本地无体积上限，生产受 `client_max_body_size` 约束，故超限行为只能在生产链路暴露。
- 首屏预取与 chunk 划分只在 `vite build` 后成立，本地 dev 模式不可见，相关回归需在生产构建产物上核验。
- 尚未引入生产构建校验命令或本地 nginx 层。当前依赖「重建镜像时源码会被重新构建」这一事实保证改动不丢失，两条链路的行为差异作为观察项，暂不额外投入。
- `scripts/migrate-from-docker.sh` 仍需 Docker（用一次性容器读卷）。属一次性脚本，原卷清理后可连同删除。

- Go 默认只信任本机代理提供的 X-Real-IP；Docker 使用 TRUSTED_PROXIES 指定代理网络（默认 172.16.0.0/12，自定义网络需调整）。Nginx 和 Vite 覆盖来自客户端的 IP 头；Go 端口不得绕过代理公开。
- SMTP 支持 implicit TLS 和强制 STARTTLS，总 IO 期限 20 秒；真实网易收信仍待私密配置后的验收。
