# 实现验证记录

**关联**：[Issue #112](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/112)、[Spec](spec.md)、[Tasks](tasks.md)

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

- 无 Conda 的干净机器从 `make locallydeploy` 入口贯通完整自动安装。
- 不同系统用户名、路径含空格的完整迁移，以及全部故障阶段的中断注入矩阵。
- 完整真实业务样本中的审核历史、结构候选附件下载及所有指纹兼容性；当前人工样本与针对性回归不能替代全场景业务验收。
- 外部模型、Embedding 和真实 SMTP 调用；部署报告始终单列未配置/未实际验收。

Issue 保持开放；未执行项不勾选，不据此宣称跨机器交付已完成。

## 用户调整验收及提交要求

2026-09-21，用户明确表示不需要 Ubuntu 24.04 验收，并要求先提交 Git 记录。
该平台测试已从必需验收中移除；此前镜像拉取的代理超时不再作为阻塞。本次依据上述
已通过的验证提交当前实现与文档，其余验收继续由 Issue #112 跟踪，不推送、不关闭 Issue。
