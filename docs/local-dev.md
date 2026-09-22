# 本地开发环境

全部本地服务（包括 GROBID）使用宿主机进程，不需要安装或启动 Docker。
前端、Python、Go 与上传 Worker 支持源码重载；资讯 Worker/Scheduler 修改后需重启。

## 快速开始

首次在新机器部署，或恢复 `make frozen` 生成的包：

```bash
make deploy CHECK_ONLY=1  # 只检查前置条件，不写配置或数据
make deploy               # 准备环境、配置和数据，再启动
```

首版面向联网 Linux x86_64 / WSL2 Ubuntu。提前准备 Bash、Make、Python 3、curl、tar、
ss、setsid。Neo4j 从官方发行归档安装，GROBID 使用官方源码和模型在本机构建；
版本及 SHA-256 固定在 `scripts/local-deploy-versions.json`。
首次安装需要访问 Conda、PyPI、npm、Go、GitHub、Gradle/Maven 与 Neo4j 官方下载服务。
若下载失败，先处理相应来源的网络访问；脚本不会退回 Docker 或跳过必需组件。
报告中的 `next_steps` 提供处理建议；系统或目标检查失败时显示环境“未检查”，不代表 Conda
不存在。预检阻塞不会创建 `.env`、`.local` 或 `.data`，脚本不自动执行系统安装或修改权限。
脚本复用兼容的 Conda `sc-wiki`，没有则创建；
找不到 Conda 时在 `.local/miniforge` 安装，不修改 shell 初始化文件。已有 `.env` 不覆盖，
缺少时生成本机随机数据库和 JWT 凭据。安装完成后 `make start/stop/status` 继续可用。

安装器与 Go 热重载共用 `GOPATH`、`GOCACHE`、`GOPROXY`；默认沿用项目已有的
`https://goproxy.cn,direct` 模块镜像，避免安装与启动重复下载。可按网络条件为本次命令
显式指定其他模块源，例如在官方源可达的机器上：

```bash
GOPROXY="https://proxy.golang.org,direct" make deploy
```

这不是系统 HTTP 代理，不写入全局 Go 配置；仍使用仓库 `go.sum` 与模块校验。
不要关闭 TLS 或设置 `GOSUMDB=off` 绕过真实性检查。

源机器在源码已提交、后台任务结束后执行：

```bash
make frozen OUTPUT="/备份目录/sc-wiki.tar.gz"
# 把压缩包和同名 .sha256 文件复制到新机器
cd "/备份目录"
sha256sum -c "sc-wiki.tar.gz.sha256"
tar -xzf "sc-wiki.tar.gz" -C "/空的部署目录"
cd "/空的部署目录/sc-wiki"
make deploy
```

打包期间会暂停当前项目的应用写入，完成或失败后恢复原运行状态。包包含业务库全部表、
Neo4j、Qdrant、上传草稿及附件，不包含旧环境、`.env` 或外部模型/邮件密钥。
目标必须为空；不支持合并覆盖或跨版本升级。AI、Embedding 和邮件需在目标另行配置，
基础部署成功不代表外部调用已验收。无包时创建空实例，并提示管理员创建命令。

`make setup` 只准备共享依赖和配置；`make migrate` 仍是旧 Docker 卷迁移脚本，不是
跨机器包恢复入口。实现与真实机器验收的边界见 [#112 验证记录](specs/112-portable-local-deployment/validation.md)。

浏览器打开 http://127.0.0.1:5173

```bash
make status         # 查看各服务状态
make logs S=python  # 跟踪日志（python/goserver/frontend/mysql/neo4j/qdrant/redis/worker）
make stop           # 停止全部
```

## WSL mirrored 与 UFW

当前本地 WSL 使用 `networkingMode=mirrored`。SC-Wiki 与 VS Code Remote WSL 都依赖
`127.0.0.1` 连通；在该模式下，本地 TCP 流量会经过 `loopback0`。宝塔安装器启用 UFW 并设置
默认拒绝策略后，UFW 默认只放行 `lo`，会阻断这部分流量，表现为 VS Code Remote WSL 无法连接或
Windows 无法打开本地服务。

本地开发环境的既定策略是让 UFW 保持停止且禁止开机启动。安装宝塔后，先检查：

```bash
sudo ufw status verbose       # 预期：Status: inactive
systemctl is-enabled ufw      # 预期：disabled
systemctl is-active ufw       # 预期：inactive
```

若 UFW 已启用，且当前确实是本地 WSL 开发环境，可恢复为本项目采用的本地策略：

```bash
sudo ufw --force reset
sudo systemctl disable --now ufw
```

`ufw --force reset` 会删除现有 UFW 规则。不要在生产服务器执行这两条命令，也不要只为 VS Code
临时放行单个端口：VS Code Server 和本地开发服务会使用多个或动态 localhost 端口。恢复后重新
连接 VS Code Remote WSL，并访问 `http://127.0.0.1:5173` 验证。故障事实与边界见
[Issue #89](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/89) 和
[Spec](specs/89-local-dev-firewall-compatibility/spec.md)。

## 服务构成

| 服务 | 地址 | 来源 | 热重载 |
|---|---|---|---|
| frontend (vite) | 127.0.0.1:5173 | `frontend/node_modules` | HMR |
| goserver | 127.0.0.1:8080 | 便携实例 `.local/go`，旧实例兼容 `~/.local/go` | 有（约 1s） |
| python (uvicorn) | 127.0.0.1:8000 | conda `sc-wiki` | 有 |
| worker (rq) | — | conda `sc-wiki` | 有（watchfiles） |
| mysql | 127.0.0.1:**3307** | conda `sc-wiki` | — |
| redis | 127.0.0.1:6379 | conda `sc-wiki` | — |
| neo4j | bolt://127.0.0.1:17687 | `.local/neo4j` | — |
| qdrant | 127.0.0.1:6333 | `.local/bin/qdrant` | — |
| grobid | 127.0.0.1:8070，管理接口 8071 | `.local/grobid`、独立 Java 17 | — |

请求链路：浏览器 → vite（`/api` 代理）→ goserver →（未命中路由反代）→ uvicorn。

MySQL 用 3307 而非 3306：宿主机 3306 已被一个系统级 MySQL 8.0（`/usr/sbin/mysqld`）占用，
与本项目无关。

`make start` 会默认启动 `news-worker` / `news-scheduler`，使资讯定时采集保持可用。只需维护资讯进程时可单独启动：

```bash
bash scripts/dev.sh start news-worker news-scheduler
```

引用解析需要在本地 `.env` 配置：

```bash
GROBID_URL=http://127.0.0.1:8070
```

`make start` 会在启动 Python/Worker 前启动 GROBID；单独维护时可使用
`bash scripts/dev.sh start grobid`、`status` 或 `stop grobid`。首次构建会下载模型与 Maven
依赖，占用较多磁盘和内存。API 和管理端口均只绑定回环地址，PID 和日志使用既有运行目录。
旧容器或其他服务占用端口时拒绝启动，不自动删除容器或接管未知服务。

## 使用 DBeaver 连接本地数据库

在 Windows 上启动 DBeaver，新建连接并选择 MySQL 驱动，然后选择 URL 模式：

| 配置项 | 填写内容 |
|---|---|
| URL | `jdbc:mysql://127.0.0.1:3307/scwiki` |
| 用户名 | `scwiki`，对应项目根目录 `.env` 中的 `MYSQL_USER` |
| 密码 | `.env` 中 `MYSQL_PASSWORD=` 后面的完整值，不使用 `MYSQL_ROOT_PASSWORD` |
| 保存密码 | 可勾选 |

如果选择主机模式，填写主机 `127.0.0.1`、端口 `3307`、数据库 `scwiki`。
本地 MySQL 服务需要已启动；如果调整过本地连接配置，以 `.env` 中的实际值为准。

填写后点击“完成”，首次连接按提示下载 MySQL 驱动。连接成功后，在左侧展开
“连接 → 数据库 → scwiki → 表”，即可查看 `papers`、`superconductors` 等数据表。

## Conda 环境

**`sc-wiki`** 同时提供应用 Python 依赖（FastAPI、pymatgen、rq 等）和本地基础服务
（mysqld、redis-server、openjdk 21、mysql 客户端）。运行 `make setup` 时会在该环境内
安装缺失的基础服务依赖。

GROBID 的 Java 17 由 Conda 安装到项目私有 `.local/grobid-java`，构建使用固定 Gradle；
不修改 `sc-wiki` 的 Java 21 或系统 Java，不新增另一套应用 Python 环境。

## 目录

```
.data/          # 全部数据，已 gitignore
├── mysql/ redis/ neo4j/ qdrant/
├── uploads/ upload_PDFs/ parsed_markdown/
├── review_artifacts/ clean_results/ avatars/
└── prop_name_ai_cache.json

.local/         # 运行时，已 gitignore
├── neo4j/          官方发行包安装的 Neo4j 5.26.29
├── grobid/         本机 GROBID 0.8.1 服务、模型及原生库
├── grobid-java/    项目私有 Java 17
├── gradle-cache/   GROBID 构建依赖缓存
├── bin/            qdrant 与编译产出的 goserver
├── my.cnf          MySQL 配置（与系统 MySQL 完全隔离）
├── run/ log/       pid 与日志
└── run-neo4j/      Neo4j 自己的 pid 目录（必须与 run/ 分开，见下）
```

Go 工具链装在仓库外的 `~/.local/go`。

## 测试

```bash
make test              # 后端 pytest
make test-go           # goserver
bash scripts/run-tests.sh frontend
```

不再需要"挂载仓库的一次性 Docker 容器"来跑后端测试。

## 本地改的代码会进入 Docker 部署吗

会。这两件事无关，不用担心「在 vite 里改了但 nginx 里没更新」。

`docker/frontend.Dockerfile` 的做法是先 `COPY frontend/ .` 拷入**源码**，再在镜像内跑
`npm run build`。nginx 拿到的是这次构建的新产物，它不持有代码副本，也不参与编译。
所以你改的每一行前端代码，重建镜像时都会被编译进去。只有改 `docker/nginx.conf`
本身才需要关心 nginx。

本地不用 nginx 是因为它和热重载互斥：nginx 提供的是 `vite build` 的已构建产物，
而热重载的前提恰恰是不构建、由 Vite 按需转译源文件。既然前端入口必须是 Vite，
nginx 剩下的 `/api` 代理职责 `vite.config.ts` 已经在做，再叠一层就是冗余。

### 真正的差异：同一份代码，两种环境行为可能不同

方向是**本地比生产宽松**，所以风险是「本地能用、生产不能用」，不是「改了没生效」。

| 差异项 | 生产 | 本地 |
|---|---|---|
| `client_max_body_size` | 50M / 51M | 无上限 |
| `proxy_request_buffering off` | 有 | 无 |
| `Accept-Encoding` 清空 | 有 | 无 |
| `removeHeavyPreloads` / `manualChunks` | 生效 | 不生效（仅构建期） |

前三项只在改上传相关功能时才有意义；第四项影响首屏加载和 chunk 划分，本地永远看不出来。
`Accept-Encoding` 那条值得留意，因为 `backend/main.py` 装了 `GZipMiddleware`，
压缩行为在两条链路上确实不同 —— 当初加这条就是为了修上传响应 JSON 截断。

当前**不引入额外机制**，把这些差异当观察项。改上传功能或排查首屏性能时，
直接起一次生产 compose 验证，比在本地维护半真半假的 nginx 层更可靠。

日后若要收敛，两条候选路径：加一个只跑生产构建、不产镜像的校验命令
（能覆盖类型错误、构建期插件、依赖缺失等多数「本地好使、镜像挂掉」的情形）；
或把 nginx 放在 Vite **前面**而非替代它（能复现前三项配置，代价是多一层调试面，
且 HMR 的 WebSocket 走代理偶发连接问题）。

## 实施过程中踩到的坑

这些都是实测结果，改动相关配置前值得先读一遍。

**Neo4j 官方下载可能返回 403。** 当前机器访问固定的 `dist.neo4j.org` 归档曾被拒绝。
旧安装器曾通过镜像提取，本次已按要求移除这条 Docker 路径。CDN 不可达时自动尝试版本
清单内的发行对象存储地址，两处均使用相同的官方 SHA-256。也可在能访问官方源的机器
下载同版本归档，放到 `.local/downloads/neo4j.tar.gz` 再重试；安装器仍核对固定 SHA-256。
不要用任意镜像包替代或关闭校验。预检通过只表示本机前置检查通过，不保证后续下载可达。

**Neo4j 的 pid 文件会与包装进程的 pid 文件撞名。** 两者都叫 `neo4j.pid`。
放同一目录时 Neo4j 会读到包装进程的 pid，误判"已在运行"并拒绝启动。
故 `server.directories.run` 指向独立的 `.local/run-neo4j/`。

**镜像里的 `data`/`logs` 是符号链接**，指向 `/data`、`/logs`。不替换成真实路径，
log4j 初始化就会失败，且错误信息完全不提符号链接。

**Qdrant 必须同时指定 storage 和 snapshots 路径。** 只给 storage 会
panic 退出（exit 101），日志里的直接线索只有一行 `.qdrant-initialized` 权限警告。

**MySQL 数据不能物理拷贝。** Docker 端是 8.4.11，conda-forge 最高 8.4.2，
MySQL 拒绝打开高版本 datadir。必须走 `mysqldump` 逻辑导出，`migrate-from-docker.sh` 已如此实现。

**所有 mysql 命令必须带 `--defaults-file`。** 系统 `/etc/mysql/my.cnf` 含
`user = mysql` 和 `log_error = /var/log/mysql/error.log`，以普通用户启动会直接失败。

**`redis-cli` 和 `mysqladmin` 在脚本里要重定向 stdin。** 否则等待输入而挂住。

**`mysqladmin ping` 在权限不足时也返回 0**（服务器活着就算通）。健康检查看似正常，
但 `shutdown` 需要 root，故统一显式带 `-uroot`。

**bash 的 `local a=$1 b="$a"` 是陷阱。** 整行会在 `local` 执行前完成展开，
此时 `$a` 尚未赋值，`set -u` 下直接报 unbound variable。必须拆成两行。

## 已知的既有问题（非本次引入）

- `tests/07_researcher_community_forum/news-feed.test.tsx` 中一个用例失败。在干净的 `HEAD` 上同样失败，与本地化无关。
- 数据库里 `papers.knowledge_graph_title` 列已存在但 `alembic_version` 未记录该 revision
  （Docker 库里也一样，说明是手工加的列）。已用 `alembic stamp head` 对齐。
