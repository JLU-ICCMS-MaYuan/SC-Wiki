# 数据模型与迁移包结构

**关联**：[Spec](spec.md)、[命令契约](contracts/cli.md)

本 Feature 不新增业务表，也不改变论文、审核、物性或表单的数据所有权。下面定义迁移制品与本机执行记录。

用户已确认同包支持本地与 Docker 目标。两端共用以下包布局、业务数据清单和校验规则；
Docker 恢复尚待实现，不增加 Docker 专用业务表或另一种 SQL 格式。目标部署记录应区分
运行方式；Docker 的宿主附件目录和应用内 `/data` 路径必须显式映射，不能共用一个路径值。

## 包布局

```text
sc-wiki/
├── Makefile、backend/、frontend/、goserver/、scripts/ 等已提交源码
└── .deployment/
    ├── manifest.json
    ├── checksums.sha256
    ├── mysql/business.sql
    ├── neo4j/neo4j.dump
    ├── qdrant/inventory.json 与 <序号>.snapshot
    ├── redis/upload-drafts.json
    └── files/ 及 paths.json
```

业务数据库或集合为空时仍有明确的组件状态和零值清单，不能以文件缺失表示空数据。源码不带 `.git`；解压后部署不依赖 Git。压缩包及其外部 SHA-256 文件默认放源仓库的 `dist/`。

## 部署清单

`manifest.json` 格式版本为整数 `1`，未知版本拒绝恢复。必需信息如下：

| 字段 | 含义与约束 |
| --- | --- |
| `format_version`、`bundle_id`、`created_at` | 格式版本、随机 UUID、UTC 导出时间；包标识不因复制而改变。 |
| `source_commit`、`files` | 40 位 Git 提交；源码和 payload 共用相对路径/大小/SHA-256 清单，排除清单自身。 |
| `services` | 版本清单全文，含支持平台、服务版本和镜像摘要，不保存源机器环境前缀。 |
| `components.mysql` | 原业务库名、全部 revision、逐表行数、规范化 DDL 摘要及对象清单。 |
| `components.neo4j` | 节点数、关系数、索引/约束定义；业务库固定为 neo4j。 |
| `components.qdrant` | 每集合名称、配置、精确点数、快照文件及别名映射。 |
| `components.redis` | 任务数量；导出时刻、每条状态/草稿及到期时刻位于 `redis/upload-drafts.json`。 |
| `source_data_root`、`paths.json` | 原数据根及受支持字段的路径映射；不保存源凭据。 |
| `capacity` | 文件与各组件恢复估算字节数，用于预检目标空间。 |

每个 payload 文件必须出现在校验清单，清单不允许重复路径、绝对路径、`..`、设备文件或链接。组件必须有明确清单，空组件以零计数/空集合表示；不可达和权限失败直接失败。外部 SHA-256 用于传输完整性，不宣称提供发布者身份认证；只接受部署者信任的私有包。

## 数据纳入规则

| 数据 | 处理方式 |
| --- | --- |
| MySQL 业务库全部表 | 保留定义、数据、主外键、索引、检查约束和迁移版本；动态表单、账户、社区、审核审计、持久草稿同样保留。 |
| MySQL 系统库和登录账号 | 不导出；目标创建本地服务账号，不复制源管理员口令。 |
| Neo4j 业务数据库 | 原生 dump；`system` 库与认证状态不导出。首版预检只允许本项目默认业务数据库 `neo4j`，额外业务数据库应阻断而非忽略。 |
| Qdrant | 全部项目集合、向量/载荷、配置及别名；来源必须为项目独占本地实例。 |
| 应用文件 | `uploads`、`upload_PDFs`、`parsed_markdown`、`review_artifacts`、`clean_results`、`avatars` 及 `prop_name_ai_cache.json`；还须检查所有被引用文件是否属于已登记映射。 |
| 模型运行配置 | 排除 `runtime/default_llm.json`；允许记录不含密钥的供应商、模型和 Base URL 元数据供目标重新配置。 |
| 日志、PID、缓存、旧二进制、Conda 环境、node_modules | 不打包，目标按源码依赖重新安装。 |

不依赖 `.gitignore` 作为唯一过滤器。出现未知业务目录或根目录外的引用时列出路径并阻断，直到显式登记映射；不自动把整个外部目录复制进包。

## Redis 上传草稿

- 只保留 `upload:<task_id>:state`、`upload:<task_id>:draft` 及由它们重建的 `upload:user:<user_id>:tasks` 关系；字段按当前上传契约校验。
- 状态和草稿携带绝对 `expires_at`，无 Redis TTL 时为 null；原状态里的 `cleanup_at` 原样保留。记录的有效期由两者较早者决定。
- 排除 `upload:llm:*`、`upload:<task_id>:lock`、全部 `rq:*`、认证、验证码和限流数据。JSON 数据不包含可执行反序列化对象。
- 当前 `RUNNING_STATUSES` 和实际队列的就绪、执行、延迟重试记录用于阻断打包；读取现有状态契约，不在脚本重新发明状态枚举。
- 恢复时核对用户 ID、论文引用及任务 ID；用户缺失或状态损坏时失败，不静默丢弃。已经过期的记录跳过并计数，因此验收满足“导出数量 = 恢复数量 + 搬迁期间到期数量”。
- 不恢复旧 job ID 作为可执行任务；保留任务业务 ID及必要历史信息，再次解析通过既有正常入口创建新作业。

## 路径映射

`paths.json` 记录 `store`、`record_id`、`field_pointer`、`source_root_id`、`relative_path`，用于把明确的文件字段映射到目标 `.data`。受支持字段登记在实现的 `paths.py`，覆盖论文文件路径、上传清单 `file_path`、持久草稿/解析产物中的文件引用及结构候选路径。

只允许源根目录内且有对应归档文件的路径。相对路径保持语义，绝对路径转换为目标根加相对路径。只转换登记的数据库列/JSON 字段，不改证据原文、论文正文、科学指纹或历史审核判断；如果路径参与现有业务校验，必须在相应读取契约层兼容并证明业务摘要不失效。发现不受支持的绝对引用时打包失败。

MySQL 行数与结构摘要不受路径转换影响；内容一致性验证应对允许变更的路径字段做规范化，而不是要求原始 SQL 字节一致。

返修并发基线包含 `PaperFile.stored_path`。目标临时库先确认哪些草稿在源路径下仍有效，
然后转换路径并只更新这些草稿的 `base_fingerprint`；不更新本就陈旧的草稿，不改变科学
核对指纹、审批或历史。这一恢复适配使用现有 `paper_revisions.fingerprint/assert_current`
进行真实回归验证，详见 [Research](research.md#实现核验补充返修草稿的路径与冲突基线)。

## 本机部署记录

路径为 `.local/deployment-state.json`，权限 0600。字段包含记录版本、操作 ID、包标识/无包源码摘要、目标根、阶段和恢复草稿计数。环境前缀与实际 Conda 包版本独立保存在 `deployment-environment.json`；结果与错误码保存在 `deployment-report.json`。三者不含密钥。

阶段按 `preflight → environment → configured → restoring/initializing → verified → promoted → started → complete` 顺序推进；错误记录 `failed_stage`，不覆盖最后成功阶段。临时目录带相同操作 ID，目录内的完成标记与记录共同判断归属。

- 提升前失败：保留诊断；下次仅可重建本操作的临时数据，不碰正式 `.data`。
- 提升后失败：下次从核验/启动恢复，绝不重新导入。
- 完成后重跑：验证本机服务和 schema 即可；业务数据允许增长，不再要求行数等于最初包，防止误判为需要重导。
- 包变更或源码/schema 不兼容：退出并提示使用新目录；首版没有原地升级。

执行锁仅用于本地并发控制，不复制源锁。状态记录不包含数据库口令，不作为任务或 Issue 完成证明。
