# 实现验证记录

**关联**：[Issue #112](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/112)、[Spec](spec.md)、[Tasks](tasks.md)

## `dist` 唯一包自动发现（2026-09-22）

本轮基于 `mayuan` 的 `f7a9dad`，按用户最新要求将“选择最新包”改为“只能保留一个包”。
`make deploy` 自动发现 `dist/` 直接子项的唯一压缩包，与显式 `BUNDLE` 共用安全解包、
清单验证及后续恢复路径；多个时先报错，`.sha256` 不计数，不删除包或回退空库。
普通入口和只读模式均在包错误时保留已有报告、配置和数据。状态归属检查从写入方法中
拆出只读 `DeploymentState.inspect()`，复用原有规则，不引入覆盖恢复。

### 验证

```bash
PYTHONNOUSERSITE=1 /home/mayuan/soft/miniconda3/envs/sc-wiki/bin/python -m pytest \
  --confcutdir="tests/02_maintenance_and_verification" \
  "tests/02_maintenance_and_verification/test_local_bundle_discovery.py" \
  "tests/02_maintenance_and_verification/test_local_environment.py" \
  "tests/02_maintenance_and_verification/test_local_deployment.py" -q -rs
make deploy CHECK_ONLY=1
make deploy
```

- 新增 **31 项全部通过**；总回归 **91 通过、11 跳过**。首轮新增测试曾出现 23 失败、2 通过，
  复现未扫描 `dist`、错误落入空库路径及普通失败改写报告的问题；后补畸形清单的 4 项也先失败，
  修复后通过。11 项跳过原因与 Conda 修正轮相同：占用端口或缺少显式隔离存储/GROBID，
  未停止当前服务，不把跳过当作通过。
- 临时目录真实 Make/Bash/Python 子进程覆盖多包、单包/零包、坏包、格式不支持、源码差异、
  同 ID 不同清单、已有空库实例及链接拒绝；对比目标目录全部文件，预检均保持字节不变。
  成功预检使用受控 Conda 替身，故只证明入口与模式选择，不证明本轮重新安装依赖。
- 人工 tar 包实际封装、解压、摘要核验、重复准备、显式来源及 `.deployment` 回退通过；
  `.env` 保留原字节。没有改动数据库导入器，也未把 `SELECT 1` 测试文件的解压称为完整数据库恢复。
- 当前真实包 `dist/sc-wiki-20260921T101043Z-6e17f649.tar.gz` 被普通与只读 Make 入口自动选中，
  报告 `mode=restore` 及包路径，随后以“当前 Git 源码与数据包不兼容”在预检退出 2。
  包来自 `6e17f649`；本轮修改前即有 23 个源码文件不同，Neo4j/GROBID 服务安装描述也不同。
- 实测前后 `.env`、`.local/deployment-state.json`、`.local/deployment-report.json`、
  `.local/my.cnf`、`.data/.deployment-owner.json`、原备份和 `sc-wiki` 环境历史摘要相同。
  未重启服务、修改密码、创建恢复记录或导入当前业务备份。
- Bash 语法、`git diff --check` 及受影响文档相对链接检查通过。

### 交付边界

T041–T043 对应唯一包发现及安全拒绝，不表示 T040 的跨源码兼容或当前实例切换已经完成。
当前包仍不能直接恢复到已有实例；按 `big-project-spec-runner` 的高影响决策门，
“保留当前源码，仅恢复兼容数据”的扩展等待用户确认，现阶段不放宽保护、不称为数据已部署。
本轮未重跑原生存储全链路、干净机器或 Docker 目标验收。

用户指南、CLI、Spec/Plan/Research/Tasks 和两份 Overview 已同步可验证行为；根 README
保留禁止自动编辑标记。GitHub #112 只读核验为 OPEN、`type:feature`，远端旧标题/正文
未在本轮更新，不关闭 Issue、不推送，不提交 `.env` 或私有备份。

## 用户准备 Conda 的职责修正（2026-09-22）

本轮基于 `mayuan` 的 `b1b1760`，按用户确认取消自动安装 Conda，只创建或复用
`sc-wiki` 并安装项目依赖。缺少或不可执行 Conda、查询失败、不兼容 Python、环境实际
指向 base 时在预检拒绝；安装器没有自动下载 Miniforge 的分支。历史版本清单字段保留，
不改变当前实例版本摘要或触发依赖升级。

### 验证

```bash
PYTHONNOUSERSITE=1 /home/mayuan/soft/miniconda3/envs/sc-wiki/bin/python -m pytest \
  --confcutdir="tests/02_maintenance_and_verification" \
  "tests/02_maintenance_and_verification/test_local_environment.py" \
  "tests/02_maintenance_and_verification/test_local_deployment.py" -q -rs
make deploy CHECK_ONLY=1
make deploy
```

- 回归 **60 通过、11 跳过**。新增 17 项全部通过，包括真实 Make/Bash/Python 子进程
  中缺失/不可执行/失败的 Conda、base 符号链接、不兼容 Python 的普通和只读预检，以及
  非默认前缀复用、待创建报告、安装器无 Conda 不下载和安装命令的环境作用域。
- Make 测试使用临时源码、受控 PATH 与 Conda 测试替身，只读检查实际 CLI 报告及文件
  字节不变；创建/安装测试核验命令参数，不把替身测试称为本轮全新 Conda 环境安装。
- 11 项跳过分别为 4 项需要空闲部署端口、2 项需要空闲 GROBID 端口、1 项未提供的
  隔离 GROBID 实例、4 项未提供的隔离存储实例；没有为测试停止当前服务。
- 本机真实预检找到用户已有 `/home/mayuan/soft/miniconda3/bin/conda` 和
  `/home/mayuan/soft/miniconda3/envs/sc-wiki`，返回 0。真实 `make deploy` 重跑返回 0、
  “基础部署成功”，11 个服务继续运行，地址为 `http://localhost:5173`。
- 实测前后 `.env`、Conda base 的 `conda-meta/history` 与 `conda list --json` 摘要相同。
  没有安装或升级 Conda、修改 base、导入 `dist`、覆盖现有数据或轮换凭据。
- Bash 语法、差异检查及本次文档相对链接检查纳入提交前验证。

### 文档与未完成边界

Spec/Plan/Research/CLI/Quickstart 已同步用户分工，T038–T039 对应本轮验证。
`docs/local-dev.md` 列明人工准备、脚本安装、外部凭据和非部署测试依赖；Overview 只记录
已实现行为。根 `README.md` 的禁止 AI 编辑标记保持，建议人工将旧 Docker 前置说明改为
“用户准备 Conda 与系统基础工具；脚本准备 sc-wiki 与本机服务，不需要 Docker”。

自动选择 `dist` 最新备份仍由 T040 澄清源码兼容规则，没有绕过原源码校验或导入当前
真实备份。既有跨机器、全业务恢复及 Docker 目标验收不据此完成，Issue #112 不关闭。
远端 Issue 正文尚含旧命令和自动 Conda/Docker 前置说明，本轮只读核验其 `type:feature`
与 OPEN 状态；当前没有 GitHub 写连接器或 `gh`，未修改远端正文、未推送。

## 完全本机部署与热重载修复（2026-09-22）

用户明确取消本地部署的 Docker 依赖。本轮在 `mayuan` 的 `f24e504` 基础上修改，
部署使用本轮工作树；完成提交前属于“运行环境领先于 Git”，不据此关闭整个 Issue。

### 实现与来源

- 预检、Neo4j 安装、GROBID 安装/启停与进程归属检查均不再调用 Docker；没有跳过必要服务。
- Neo4j 5.26.29 使用官方发行归档与官方 Dockerfile 声明的 SHA-256。CDN 返回 403 后，
  从发行对象存储下载成功，摘要为 `a45ca9644100d995500f7ea7f5bb4874e16e588891fdfbdff65d21321331caa2`；
  该地址已加入固定备用来源，仅传输失败回退，摘要失败直接拒绝。
- GROBID 0.8.1 官方源码、Wapiti 模型及原生库使用项目私有 Java 17.0.18、Gradle 7.6.4
  构建。实测 `installDist` 遇到重复依赖，改用上游已配置重复处理的 `distZip` 后通过。
  Java 17 不替换应用环境的 Java 21；API 8070 和管理接口 8071 均监听回环地址。
- 实测发现安装器与 Go 启动脚本的 GOPATH/GOPROXY 不一致，导致安装后重复下载；现已
  共用 `environment.go_environment()`，保留原运行脚本的模块源与缓存默认值、尊重显式覆盖。
  不修改全局 Go 配置或系统代理，不关闭 TLS/模块校验。

### 自动化与真实进程证据

- 通用回归：`pytest-unit.log` 记录 **48 通过、4 跳过、1 未选择**；四项跳过为未配置的隔离
  MySQL/Redis/Qdrant 测试，未选择项为单独执行的 GROBID 实测。之后新增 Go 配置回归，
  Go/安装失败阶段/备用源专项 **3 通过**（其中两项是复验，不能重复计数）。
- 显式人工 GROBID 实例：**1 通过**。真实构建、引用解析、PDF 转 TEI、双端口进程归属、
  重复启动复用同一 PID、停止释放端口通过；PATH 中放置会失败的 Docker 命令，确认未调用。
- 新增测试还覆盖 Docker 缺失/不可用不影响真实 CLI 预检、下载与构建失败不发布半成品、
  未知目录不覆盖、ZIP 越界拒绝、备用源同摘要与缓存复用、安装失败正确记录 environment 阶段。
- Bash 语法、`git diff --check`、受影响文档相对链接检查通过。

### 当前机器完整部署

环境为 Ubuntu 26.04 x86_64，使用已有 `/home/mayuan/soft/miniconda3/envs/sc-wiki`。
起始不存在项目 `.env`、`.data` 或运行实例。本轮实际执行完整部署，结果为退出 0、
`基础部署成功`、阶段 `complete`，而非只启动独立前端。

- Python 依赖导入/`pip check`、npm 安装、Go 模块校验、全部本机基础服务安装通过。
  首次 Go 官方源超时，单次命令指定项目原有模块镜像后通过；之后已修复共享 Go 配置。
- MySQL 完整空库迁移建立 51 张表，保留 `20260914_0052`、`20260918_0108` 两个分支，
  元素种子与真实 schema 核验通过；临时数据验证后提升为正式 `.data`。
- `make status` 的 11 个服务均运行；数据库认证/查询、GROBID、前端 → Go → Python 的
  `/api/form-definitions` 链路、上传 Worker 注册和资讯进程检查通过。访问入口为
  `http://localhost:5173`（实际监听 `127.0.0.1:5173`）。
- 在 Docker 命令被替换为失败桩的环境再次执行 `make deploy`，退出 0，没有调用 Docker；
  `.env` SHA-256 与 operation_id 前后相同，没有重复初始化或旋转凭据。
- 对 `frontend/src/App.tsx`、`backend/main.py`、`goserver/main.go` 临时添加注释探针：
  收到 Vite WebSocket 的真实 `js-update`；Uvicorn 更换服务进程、Go 重编译启动、上传
  Worker 更换进程并重新注册，随后健康检查恢复 200。移除探针后，三文件 SHA-256 与测试前
  完全相同，没有把测试改动留进业务代码。

本机诊断目录为 `/tmp/scwiki-native-112-HRYz9n`，主要日志为 `build-distzip.log`、
`pytest.log`、`pytest-unit.log`、`deploy-native.log`、`redeploy.log`。人工实例已停止；
仓库内正式新实例保留运行。第一次失败安装的状态文件只移到该临时目录保存，未清理用户数据。

### 验收边界

- 浏览器技能连接返回无可用浏览器，列表为空；没有执行页面点击/视觉验收，HTTP 和 HMR
  协议测试不冒充浏览器验收。AI、Embedding、SMTP 未配置，没有调用付费模型或发送邮件。
- 本机仓库位于 `fuseblk`，MySQL 初始化及迁移明显较慢；该挂载未呈现逐文件 0600 权限
  （显示 0755），上层 `/home/mayuan` 为 0750。不能把本机结果当作多用户生产权限验收；
  原生 Linux 文件系统权限与 Ubuntu 22.04/WSL2 干净环境矩阵仍由原任务跟踪。
- 根 `README.md` 标明禁止 AI 自动编辑，已保留。人工修订建议：将本地部署章节的 Docker
  前置说明替换为“所有组件在本机运行，依赖下载需要网络”，并继续链接已更新的本地指南。
- npm 安装报告既有依赖审计告警；本次未执行会改变依赖契约的 `npm audit fix --force`。
- 未完成跨用户名/跨机器完整搬迁、全故障矩阵及独立 Docker 目标恢复；T023、T026–T028、
  T031–T033 等原未完成项保持未完成，Issue #112 不关闭。

## 当前机器本地依赖与存储验证（2026-09-21 晚间）

本轮基于 `a8a69eb`，环境为 Ubuntu 26.04 x86_64。已在用户的 Conda 安装
`/home/mayuan/soft/miniconda3` 下创建 `sc-wiki`，实际验证 Python 3.12.14、MySQL 8.4.2、
Redis 8.10.1、Java 21.0.9、Node 22.21.1；安装 `docker/requirements.txt` 和 pytest，
`PYTHONNOUSERSITE=1 python -m pip check` 通过。这里的 requirements 路径是依赖清单，
不表示这些服务在 Docker 内运行。

使用临时目录 `/tmp/scwiki-112-native-tests-fAFKzk` 中的独立 MySQL、Redis 宿主进程，
动态分配回环端口，执行 `tests/02_maintenance_and_verification/test_local_deployment.py`：
**43 项通过、1 项跳过**。真实验证包括空库全部迁移及元素种子、返修路径和指纹、
MySQL 原生导出恢复/事件检查、Redis 草稿与凭据排除；Qdrant 无隔离实例故跳过。
测试日志为该目录 `pytest.log`，结束后两个测试进程均已正常停止，人工数据保留供检查。

当前报错原因已核验：Docker 服务为 active，系统组已包含 mayuan，但当前会话的附加组
不包含 Docker socket 所属组，无法访问权限为 0660 的 socket。Docker Hub 连接仍超时；
Qdrant 官方制品下载重试三次也超时，Neo4j 官方归档地址返回 403。

用户强调 `make deploy` 应支持本机源码热更新。现有前端、Python、Go 已采用宿主热更新
启动命令，但本机尚未完成整套服务启动及热更新实测。是否把 GROBID 容器和 Neo4j 镜像提取
一起改为完全无 Docker 路径，尚待澄清；本次没有删除 Docker 检查，也未启动独立前端。
上述存储测试不表示 `make deploy` 已修复或 Issue 已完成，原未完成验收保持未完成。

## 当前实例冻结检查修复（2026-09-21）

本轮用户明确授权实际执行当前实例的 `make frozen`。首次真实执行触发旧事件检查后，
恢复 Python 时又暴露终端 DEBUG=release 不符合布尔设置的问题；Python 已用修正后的
项目配置/默认值恢复并通过健康检查。当前管理员只读检查证实：MySQL 3307 的调度为 ON，
全实例启用事件为 0、执行线程为 0；业务账号缺少全局事件和线程可见权限。

修复使用同实例的项目管理员配置检查元数据，核对实例 UUID 和全局 EVENT 权限；
不改变调度开关，停服务前、导出前后和发布前检查风险。当前数据目录中的历史 SQL
备份 backups 和 pytest 临时目录 tmp 排除，其他未知目录仍拒绝。恢复不再继承无关 DEBUG。

本阶段验证：新增回归先失败再通过，部署工具 40 项通过、4 项隔离存储用例未配置而跳过；
另外创建独立 MySQL 8.4 容器，真实验证调度 ON 下禁用事件允许、启用事件拒绝、完整原生
SQL 导出/恢复（约束、触发器、例程、事件、中文及二进制）通过。当前实例事件只读检查通过。

随后在已提交且干净的 `mayuan` 源码 `6e17f649605083678564c0a78a6df0642ce394d5` 上
实际执行 `make frozen`，**退出 0**，报告“打包成功，源服务已恢复”。本机产物：

- `dist/sc-wiki-20260921T101043Z-6e17f649.tar.gz` 及同名 `.sha256`，大小 11,776,744 字节。
- 包标识 `48eff388-e561-4b77-ab17-6aa363bcbca2`；1,427 个清单文件、51 张 MySQL 表、
  1 个 Qdrant 集合、1 份 Redis 草稿，以及 Neo4j 业务 dump 和应用附件。
- 外部 SHA-256、包内逐文件大小和摘要、完整文件集合均通过；未包含 `.env`、历史 SQL
  备份、测试临时目录或模型运行凭据目录。私有数据包留在本机，不提交或上传。
- 源 MySQL/schema、Neo4j/Qdrant 查询、Redis、前端至 Go/Python 表单链路、GROBID 健康、
  Worker/资讯进程与 RQ 注册检查通过；MySQL `event_scheduler` 仍为 ON，未改调度配置。

本次证明当前实例冻结、包完整性和源服务恢复成功；没有在另一机器恢复此业务数据包，
也没有实现 Docker 目标恢复，不据此关闭整个 Issue #112。

## 打包命令更名（2026-09-21）

按用户纠正后的拼写，将 `make pack` 改为 `make frozen`，保留 `OUTPUT` 参数及内部
`scripts/pack.sh`。当前使用说明、提示及完整演练调用已同步；下文历史记录保留原命令名。
本次复用原有实现，不改变数据库事件检查、停写或恢复逻辑；此前 MySQL 调度开关阻塞
仍待独立处理，不能把更名当作该问题已修复。

验证：部署工具回归 32 项通过、4 项真实存储测试因未配置隔离实例而跳过；
`make -n frozen` 及含空格 `OUTPUT` 路径、参数安全回归、Bash 语法和差异检查通过。
未执行真实打包，未停止或重启当前服务。

## 本地部署命令更名（2026-09-21）

按用户要求，当前入口由 `make locallydeploy` 改为 `make deploy`；保留内部
`scripts/locallydeploy.sh`，部署行为、`BUNDLE` 和 `CHECK_ONLY` 参数不变。
下文历史执行记录保留当时的命令名，不代表旧 Make 目标仍可使用。

- 部署工具回归：32 项通过、4 项真实存储测试因未配置隔离实例而跳过。
- `make -n deploy CHECK_ONLY=1`、Bash 语法和差异检查通过；Make 参数安全用例覆盖新入口。
- 实际 `make deploy CHECK_ONLY=1` 已进入部署预检，因当前实例端口/回环监听配置与目标
  部署契约不一致退出 2；未进行安装或数据恢复，不将此结果报告为完整部署成功。

## 验证环境与边界

2026-09-21，在 Ubuntu 22.04.5 / WSL2、Linux x86_64 上验证。源码基于 `mayuan`，
验证时实现位于工作区；隔离测试使用临时源码副本和人工数据库，不操作当前开发实例。
测试副本使用独立端口、目录、PID 和 GROBID 容器；临时 Git 提交仅用于验证源码身份，
不表示主仓库功能已经推送。

## 已通过的验证

| 范围 | 证据 |
| --- | --- |
| 存储与保护边界 | `local-deploy-roundtrip.sh`：21 项通过，包含真实 MySQL/Redis/Qdrant、坏包和越界路径、已有数据保护、安全 dotenv、Make 参数传递、草稿主键与路径转换、部署锁并发及符号链接拒绝。最新日志 `/tmp/scwiki-112-tests-complete.log`。 |
| 从零迁移 | MySQL 8.4 完整执行两条迁移分支，得到 51 张受测表及 118 个元素；缺列和非空初始化被拒绝。MySQL 8.4.2 与 8.4.11 的检查约束编码差异已规范化。 |
| MySQL 原生迁移 | 真实导出/导入约束、中文文本、二进制、触发器、例程、视图与事件；DEFINER 转换不修改正文中的同形文本。 |
| 返修保护 | 使用真实 `fingerprint/assert_current`：换路径后原有效返修基线仍可用；原有冲突仍返回 409，草稿中的科学指纹和证据原文不变。 |
| Neo4j | 真实业务 dump/load，保留 2 个节点、1 条关系及约束/索引；目标使用独立密码，不导入 system 库。 |
| 新环境依赖 | 临时全新 Conda 环境实际安装 Python 3.12.14、Node 22.21.1、MySQL 8.4.2、Redis 8.10.1、Java 21.0.9；Python 依赖安装及 `PYTHONNOUSERSITE=1 pip check` 通过。MySQL 认证所需 PyMySQL RSA 依赖已补齐。 |
| 官方制品 | Miniforge、Go、Qdrant 真实下载与 SHA-256 校验通过；经校验的 Miniforge 已安装到测试私有目录，`conda --version` 为 26.7.2。 |
| 空实例启动 | 临时副本完成所有 11 个服务启动、数据库认证、HTTP 健康与 Worker 注册，重复部署保留配置和数据库。 |
| 实际打包 | 临时 Git 源码实例执行 `make pack` 成功，源服务恢复；活动资讯任务时曾明确拒绝发布，导出错误后也恢复应用。 |
| 业务链路 | 恢复副本通过 Vite → Go → Python 的表单定义读取、原账号登录、论文和个人资料读取，附件重定位及文件摘要一致。 |
| Go 与基础检查 | `go test ./...`、Bash 语法、Python 编译和差异空白检查通过。 |

完整 CLI 测试已退出 0，输出：`PASS: 真实 CLI 打包、异目录恢复、账号/表单/附件/草稿/图/向量、重跑及停止后重启`。
本次完整演练日志为 `/tmp/scwiki-112-cli-proof2.log`，测试工作区为
`/tmp/scwiki-112-cli-proof2`；这些临时人工数据不提交 Git。
加入源服务归属、服务版本、恢复引用和 MySQL 事件调度保护后，再次完整演练也退出 0，
日志 `/tmp/scwiki-112-cli-release.log`，工作区 `/tmp/scwiki-112-cli-release`。
之后只调整包临时文件权限及锁的符号链接保护，真实归档和锁回归已通过，并已纳入
上述 21 项测试。所有本次测试进程已停止；当前业务实例未停止或恢复数据。
本轮修复了原 `shutdown nosave` 导致草稿在恢复后重启丢失的问题；不得用
“Redis 内存导入成功”代替停止再启动后的回读。

## 可重复运行的命令

```bash
# 自动创建并清理本次独立数据库容器
bash tests/02_maintenance_and_verification/local-deploy-roundtrip.sh

# 使用已准备的依赖；运行的 Python 必须属于隔离测试 sc-wiki 环境
PYTHONNOUSERSITE=1 /测试环境/envs/sc-wiki/bin/python \
  tests/02_maintenance_and_verification/local-deploy-cli-roundtrip.py \
  --tools-from /已准备工具和前端依赖的测试源码目录 \
  --workspace /尚不存在的测试目录
```

第二项测试动态分配端口，构造人工账号、论文、附件、Redis 草稿、图与向量；实际
执行空部署 → 打包 → 异目录恢复 → 重跑 → 停止再启动。结束只停止本次测试进程和
删除本次 GROBID 容器，保留临时文件供排查。它复用了依赖，不覆盖无 Conda 的完整
首次安装入口，也不替代不同用户名或不同机器的验收。

## 尚未完成的验收

- 无 Conda 的干净机器从 `make deploy` 入口贯通完整自动安装。
- 不同系统用户名、路径含空格的完整迁移，以及全部故障阶段的中断注入矩阵。
- 完整真实业务样本中的审核历史、结构候选附件下载及所有指纹兼容性；当前人工样本与针对性回归不能替代全场景业务验收。
- 外部模型、Embedding 和真实 SMTP 调用；部署报告始终单列未配置/未实际验收。

Issue 保持开放；未执行项不勾选，不据此宣称跨机器交付已完成。

## 用户调整验收及提交要求

2026-09-21，用户明确表示不需要 Ubuntu 24.04 验收，并要求先提交 Git 记录。
该平台测试已从必需验收中移除；此前镜像拉取的代理超时不再作为阻塞。本次依据上述
已通过的验证提交当前实现与文档，其余验收继续由 Issue #112 跟踪，不推送、不关闭 Issue。

## Docker 前置失败回归（2026-09-21）

本轮机器是 Ubuntu 26.04 x86_64，系统 Python 3.14.4；没有 Docker、Conda 或此前记录的
隔离测试实例。前文 Ubuntu 22.04 / WSL2 证据属于先前环境，不是本轮重新运行的结果。
本轮不改变 SC-001 的平台验收基线，也不声称已验收 Ubuntu 26.04 完整应用栈。

修改对应 FR-002/014/017：系统工具和 Docker 检查由 `environment.py` 负责，CLI 仅汇总
`problems`、`next_steps`、错误码和实际检查状态。Conda 因前置阻塞未检查时，不再显示
“将创建 sc-wiki”。沿用 Docker 为系统前置条件的 Research/Plan 决策。

测试依赖仅安装在 `/tmp/scwiki-112-regression-QBsSBV/venv`，没有修改系统 Python。
执行命令：

```bash
/tmp/scwiki-112-regression-QBsSBV/venv/bin/python -m pytest \
  --confcutdir="tests/02_maintenance_and_verification" \
  "tests/02_maintenance_and_verification/test_local_deployment.py" -q -rs
```

结果：**28 项通过，4 项跳过**。跳过项分别为真实空 MySQL 迁移、Redis 草稿恢复、MySQL
原生导出恢复和 Qdrant 快照恢复；缺少显式隔离存储实例，未把跳过计为通过。
上层通用测试配置依赖尚未安装的 SQLAlchemy，故按 Quickstart 使用 `--confcutdir`，
本次测试不使用上层 fixture。

- 真实 Bash/Python 子进程入口：在含空格的临时目标目录和受控 PATH 下，覆盖 Docker
  命令缺失及返回失败（模拟不可用）的四种组合，普通部署与 `--check-only` 都退出 2，
  不创建配置/状态/数据，不泄漏模拟 Docker 错误输出。
- 本机实际执行 `make locallydeploy` 和 `make locallydeploy CHECK_ONLY=1`，均因缺少
  Docker 阻塞，包含操作建议及 `preflight_failed`，没有进入依赖安装或数据初始化。
- 单元故障注入：Docker 查询超时、低磁盘空间、下载损坏/离线/中断；失败下载保留原缓存、
  清除本次 `.partial`。端口冲突使用真实回环监听；不把注入测试当作真实断网或满盘演练。
- Bash 语法与 `git diff --check` 通过。原有配置保护、归档校验、路径转换和操作锁回归通过。

完整安装、服务健康、原生存储往返、换用户名及审核/结构附件场景仍待 Docker 和隔离依赖
就绪后执行。系统安装和权限变更需另行授权。本轮只更新本地实现及验证产物，没有更新或关闭
远端 Issue #112，也没有推送。

## 旧 GROBID 容器导致打包失败（2026-09-21）

用户实际运行 `make pack` 得到 `docker 执行失败（退出 1）`。本轮当前机器 Docker 可用，
运行容器名为 `scwiki-grobid`，而打包端口检查查询 `scwiki-grobid-<目录哈希>`；
该名称不存在。只读 `docker inspect` 返回 1；调用原端口检查复现同一错误，未停服务或导出数据。

修复只在打包调用 `check_ports(check_grobid=False)`：GROBID 不保存迁移业务数据，
打包不会操作它；数据库和应用进程归属仍校验，部署默认仍拒绝其他项目的 GROBID。

验证：

- 新增回归先运行得到 2 项失败、1 项通过，再修复得到部署工具 **31 项通过、4 项跳过**。
  跳过的是未配置显式隔离 MySQL/Redis/Qdrant 的真实存储用例，不计作通过。
- 对当前实例实际执行 `Runtime(...).check_ports(check_grobid=False)` 通过；该检查只读，
  没有屏蔽实际数据库端口或伪造进程归属。
- 未在当前业务实例重新执行完整 `make pack`，不声称所有后续导出与源服务恢复均已验收。
- 用户确认“本地实例打包，同一份包可用于本地或 Docker 部署”；已回写需求及适配方案，
  Docker 入口与同包两端恢复仍未实现/验收，见 T031–T033。
