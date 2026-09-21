# 验收说明：跨机器本地部署

**关联**：[Spec](spec.md)、[Tasks](tasks.md)、[CLI](contracts/cli.md)

> 命令已实现并进入隔离验证。下列场景是完整验收要求，未执行场景不得标记通过；本机测试不代替另一台干净机器验收。实际证据见 [验证记录](validation.md)。

## 前置条件

- 使用可丢弃的 Ubuntu 22.04 x86_64 或 WSL2 Ubuntu 测试实例，能联网下载依赖，当前用户可写部署目录。用户已取消 Ubuntu 24.04 必需验收。
- 准备 Bash、Make、Python 3、curl、tar、ss、setsid；源端有 Git，Docker 已安装、运行且当前用户可访问。
- 禁止用正式数据库做故障注入；每组演练使用独立目录、数据库进程及其测试端口空间，不能和当前工作实例混用。
- 使用人工构造的测试数据：两个角色账号、公开/待审/驳回论文、动态表单与物性、持久草稿与 Redis 草稿、审核历史、结构附件、PDF、头像、Neo4j 节点/关系和 Qdrant 点/别名。
- 仅使用假 API Key、假 SMTP/JWT 值进行排除检查。真实业务迁移包包含账户及未公开论文，按私有数据保存，不上传 GitHub。

## 场景 A：空机器无包部署

在包含已实现 #112 代码的干净源码目录执行：

```bash
make locallydeploy CHECK_ONLY=1
make locallydeploy
make status
```

预期：首次检查给出真实缺项而不写文件；部署准备私有 Conda 和 `sc-wiki`、全部依赖、新 `.env`、空业务库及 118 个元素。网页入口为 `http://127.0.0.1:5173`。没有默认网站账号，部署输出指向既有 `backend.scripts.create_superadmin`，并提供在已加载本机环境中调用它的方法。

第二次部署不得改变 `.env` 摘要或重复初始化。保存两个环境样本：无 Conda；已有非默认前缀且兼容的 `sc-wiki`，后者必须复用原前缀。

## 场景 B：源端打包

在隔离源实例导入测试数据，确认没有待执行、执行中或延迟重试作业；记录基准清单和运行服务。提交全部源码变更后执行：

```bash
make pack OUTPUT="/tmp/sc-wiki-migration.tar.gz"
sha256sum -c "/tmp/sc-wiki-migration.tar.gz.sha256"
```

预期：生成源码与数据包、外部校验文件；停写结束后源服务运行状态恢复，源库 schema 和数据未被迁移命令更改。检查全表/对象、图、向量及文件清单；解压后的源码不能含 `.git`、源 `.env`、依赖安装目录或任何植入的假密钥。

再次设置活动/排队作业后执行：必须拒绝发布新包，不终止原作业、不覆盖已有输出。模拟任一数据库不可达或引用文件缺失，也必须明确失败。

## 场景 C：另一机器恢复

将包与校验文件复制到干净目标机器。目标用户名和路径不同于源机器；本示例目录使用空格，以覆盖路径处理。

```bash
sha256sum -c "/tmp/sc-wiki-migration.tar.gz.sha256"
mkdir -p "$HOME/scwiki deployment test"
tar -xzf "/tmp/sc-wiki-migration.tar.gz" -C "$HOME/scwiki deployment test"
cd "$HOME/scwiki deployment test/sc-wiki"
make locallydeploy CHECK_ONLY=1
make locallydeploy
make status
```

解压前检查归档成员只在 `sc-wiki/` 内，拒绝绝对/上级路径和越界链接；只操作自己生成且信任的包。文件名示例固定，实际迁移可使用默认时间戳名称。

预期：无需旧 `.env`，自动发现 `.deployment`；目标生成新服务凭据，旧网站账号密码仍可使用，旧登录令牌失效。验证：

- MySQL 全部表与逐表行数、规范化 DDL 摘要、revision 集合及外键/检查约束符合清单。
- Neo4j 节点/关系/索引/约束及 Qdrant 精确点数、集合配置和别名一致。
- 所有附件 SHA-256 一致；页面能打开 PDF、结构附件和头像。
- 表单定义、论文状态与修订号、审核历史和证据保持不变。
- 未过期草稿可继续编辑；过期记录按原时间跳过并计数，不继承 API Key、不恢复旧 RQ 作业。
- 浏览器 → Vite → Go → Python 的实际读取链路通过，Worker 有有效注册。缺少 AI/SMTP 凭据时只报告基础部署成功。

## 场景 D：重复执行与失败保护

| 场景 | 操作与期望 |
| --- | --- |
| 成功后重跑 | 增加一条目标测试业务数据后再次部署；新数据保留，原包不重导，`.env` 不变。 |
| 非空目标 | 在未带本次部署记录的目录准备数据；部署拒绝，原文件/数据摘要不变。 |
| 换包或换源码 | 指定不同 BUNDLE 或修改关键源码；要求新目录或匹配源码，不自动升级。 |
| 不兼容环境 | 已有 `sc-wiki` 的 Python 非 3.12；退出且环境未被重建。 |
| 配置解析 | 密码含空格、引号、美元字符时正确读取；命令替换字符串不能产生任何执行副作用。 |
| 包/路径异常 | 篡改 payload、增加越界成员、缺组件或未知格式版本；导入前失败。 |
| 迁移异常 | 未知 revision、只携带一个并行分支或真实列与版本标记不符；失败，不 stamp。 |
| 端口冲突 | 其他实例监听相同端口且健康接口返回成功；仍拒绝复用。 |
| 中断恢复 | 分别在安装、导入中、核验后、目录提升与状态写入之间、应用启动时中断；重试只操作本次归属目录，不重复导入已提升数据。 |
| 源恢复失败 | 包生成后模拟源服务无法重启；命令非零，报告包路径及恢复失败，不隐瞒源状态。 |
| 外部功能 | 无凭据时不发模型或邮件请求；之后配置真实服务的验收另行记录，不以健康检查代替。 |

## 自动化验证入口（实现后）

```bash
bash -n "scripts/locallydeploy.sh" "scripts/pack.sh" "scripts/setup-local.sh" "scripts/lib-local.sh" "scripts/dev.sh"
conda run -n sc-wiki python -m pytest "tests/02_maintenance_and_verification/test_local_deployment.py" -q
bash "tests/02_maintenance_and_verification/local-deploy-roundtrip.sh"
```

真实 MySQL 迁移测试必须显式连接隔离测试库；不能把无数据库情况下的 skip 算作通过。依赖安装、数据库原生导出恢复和多进程停写不得全部 mock 后就关闭任务。

## 验收记录要求

记录系统版本/架构、源码提交、包标识、依赖版本、测试场景结果、耗时/空间、失败重试证据，以及未配置/未验收的外部能力。不记录凭据和真实论文内容。规划阶段没有以上实测结果，T022–T023 保持未完成。
