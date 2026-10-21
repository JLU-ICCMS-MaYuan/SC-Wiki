# 实施与验收记录

2026-10-21：创建 #146 并关联 #130。初始工作区 clean，mayuan HEAD 1024c5d。GitHub 仍为 1e114de，三个应用镜像该版构建成功。
服务器 Ubuntu 24.04 amd64，4 核约 16 GiB，根目录可用约 942 GiB。此前未安装 Docker；本轮已启动官方 Ubuntu 软件源 Docker/Compose 安装。
DNS www 和根域均指向目标；备案按用户要求不阻塞准备。所有业务与迁移验收当前未完成。

## 第一轮实现与验证

- Docker Engine 29.1.3、Compose 2.40.3 已通过 Ubuntu 软件源安装到目标服务器。
- 源端实测 MySQL 8.4.2、Redis 8.10.1、Neo4j 5.26.29、Qdrant 1.19.0、Garage 2.4.1。MySQL 两个 schema head 为 20261020_0049、20261020_0143b。
- 源端有 3 名用户、3 个持久草稿、0 篇正式论文、0 条物性记录、89 个 S3 对象共 27,191,813 字节；Neo4j 2 个节点、0 条关系。三个 RQ 队列排队、运行、延迟均为 0。此为盘点快照，不是最终冻结清单。
- Go 全量测试通过。生产配置/备份、文件存储协议、上传文件工作流及资讯编排定向 Python 测试 31 通过。
- 首次扩大测试因没有测试 JWT 环境而在导入阶段失败；补隔离测试配置后暴露旧测试仍用 legacy parser_profile，按当前 complementary 契约修正后通过。
- 本地和目标直接访问 Docker Hub registry 超时；目标 GitHub 与证书签发端可访问。已新增手动镜像导出工作流，尚未推送/运行。
- 三项目配置解析、无跨组 depends_on、数据无公网端口、应用与计算临时卷隔离、对象内容/元数据完整恢复及非空目标拒绝已经测试。
- 当前未迁移源数据，未开放网站；配置和测试通过不等于真实服务器验收。

## 维护窗口发现的退出缺陷

恢复演练快照前，社区消费者收到正常停止信号后重新进入 while 循环，导致 supervisor 等待子进程退出。已修复消费者在 RQ 明确停止后返回，并增加退出回归测试；部署和该测试共 7 项通过。
确认全部队列无排队、运行或延迟任务、网站与调度均已停止后，仅结束旧版本空闲子进程，让 supervisor 完成退出；未终止运行任务。随后源端进入冻结，MySQL/Redis 和全部 89 个 S3 对象已导出，后续步骤继续进行。
同时修正 Redis 容器读取宿主机 0600 私有配置的权限边界：容器启动时复制为 redis 用户私有临时配置，宿主机原件仍只读且保持 0600。

## 恢复演练结果与科学数值完整性

- 本机备份：`/Users/mayuan/SC-Wiki-backups/2026-10-21-182007-aliyun-rehearsal/`；私有原配置单独保存，没有上传源凭据。
- 可移植包 `migration-portable.tar.gz` 为 79,315,472 字节，位于服务器 `/opt/scwiki/incoming/rehearsal/`；归档 SHA-256 和 630 个清单文件逐项验证通过。首个 macOS tar 包含 AppleDouble 目录项而被严格解包检查拒绝，改用 Python 标准 tarfile 创建后通过，没有放宽路径保护。
- 阿里云独立 MySQL 8.4.2 容器 `scwiki-rehearsal-mysql` 已恢复；不公开数据库端口，通过临时 SSH 隧道核验。镜像从 Docker Official Images 的公开 ECR 分发取得并固定 digest，应用镜像仍计划由 Docker Hub 发布。
- 第一次恢复 67/68 张表内容一致；`spectrum_runs.result_json` 的 4 行、23 处 float 经 JSON 文本解析变化一个 double 末位。目标同机 SELECT 实验证明 SQL DOUBLE 转换能保持源值；新增 JSON 原文补充和受保护事务修复，不使用容差宣布成功。
- 第二次维护窗口确认源库仍与原备份完全一致，导出 34 张表的 JSON 原文；补充清单绑定 SQL、JSON 和原库存量清单的 SHA-256。本机再次正常恢复，社区 Worker 修复后的停止流程通过真实演练。
- 仅修复隔离目标的上述解析舍入后，68 张表、6,487 行的结构、数量、全部内容摘要及 schema 完全一致。证据文件：`mysql-restored-exact-inventory.json`；源库没有修改。
- 本机独立 Garage 2.4.1 新节点恢复 89 对象并完整回读，键、内容、大小、Content-Type 与自定义元数据一致。独立实例已停止，目录及证据保留。
- Redis 的旧 JSON cleanup_at 不能覆盖实际 PERSIST 事实；修复迁移按真实 TTL 恢复后，独立 Redis 中 3 个草稿均完整恢复且仍无过期时间；补真实 Redis 回归。临时锁、验证码和模型短期凭据未导入。
- 本机独立 Qdrant 1.19.0 从快照恢复 1 集合、0 个向量点，配置和别名一致；独立 Neo4j 5.26.29 从 dump 恢复，2 个节点、0 条关系及索引/约束一致。两个实例均已停止，原实例持续运行。零向量点不能冒充 RAG 检索命中验收。
- 源端真实依赖检查（含完整 schema、Redis、S3、Qdrant、Neo4j、GROBID）全通过。修正 Qdrant SDK 不支持上下文管理器的问题，使用显式 closing 释放连接。
- 最终本轮定向 Python 回归 34 通过；Go 全量测试此前通过且 Go 此后未修改。当前工作仍未完成正式上线、云端全栈业务、HTTPS 和生命周期验收。
- Git push 单独授权仍待用户回复；不得把已经提交或备份演练完成写成网站已上线。
