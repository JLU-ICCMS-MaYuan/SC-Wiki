# 实现验证记录

**关联**：[Issue #112](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/112)、[Spec](spec.md)、[Tasks](tasks.md)

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
完整冻结产物与服务恢复结果在实际执行后补充，不用这些局部验证替代。

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
测试副本使用独立端口、目录、PID 和 GROBID 容器；临时 Git 提交仅用于测试
`git archive HEAD`，不表示主仓库功能已经提交或推送。

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
