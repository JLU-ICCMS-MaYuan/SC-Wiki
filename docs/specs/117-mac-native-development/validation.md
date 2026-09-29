# 验证记录

日期：2026-09-29。平台：macOS arm64；系统 Bash 3.2；用户 Conda 的独立 sc-wiki/Python 3.12 环境。

## 已验证

- 官方 Go、Qdrant、Neo4j、GROBID/Gradle 制品摘要通过；Conda 数据库、Java、Node 与 Python 依赖安装完成，pip check 通过。GROBID 在本机从官方源码构建成功。
- make deploy CHECK_ONLY=1 对历史 Linux 包明确拒绝；对本次定向迁移包通过。旧 dist 原包及摘要保存在 .local/backups/original-linux-bundles/，未改写原包。
- 从旧 Lima 实例逻辑导出后，经受控定向转换使用真实 make deploy 恢复。54 张表、3595 条记录的结构/数量一致；Neo4j 节点及索引、Qdrant 集合配置与数量一致；17 个 PDF/Markdown 文件字节摘要一致；恢复 1 条未过期上传草稿。
- 11 个服务均在 macOS 原生进程中运行。主页、Python/Go 健康接口、论文、表单、社区统计与 RAG 健康接口共 7 个检查返回 200；RQ Worker 注册检查通过。
- make stop 后全部契约端口释放，make start 成功恢复。TCP 等待状态不再被误判为服务占用。
- 实际保存当前工作区文件后，Python 与 Go 监听进程变化，Vite 记录页面重载；不存在源码构建副本同步步骤。
- 原生 GROBID 从本机合成 PDF 提取到 1 条参考文献，不调用外部 LLM，不写业务论文。
- 定向回归：90 通过、24 跳过。跳过项为需要显式隔离数据库/解析环境、Linux 专有命令或被当前实例占用的固定端口；另有本机真实部署、停启、存储恢复及解析验证覆盖主路径。Linux 命令路由及原清单测试通过，未宣称完成 Linux 服务器实机部署。
- Bash 语法、Python 编译和 git diff --check 通过。仅本任务修改进入提交，#116 业务代码未改动。

## 本机配置修正

.env 已保留全部非空凭据，修正旧 Linux 数据目录、删除重复空 SMTP 占位，并将旧 LLM<n>_PROVIDER_NAME 改为 #116 已实现契约的 LLM<n>_NAME；3 组编号配置可解析。原文件以私密权限备份于 .local/backups/environment-before-mac.env。

## 收尾验收

- make frozen 的未提交源码拒绝门槛已验证；真实冻结包和隔离恢复将在实现提交后验收，当前不能据此宣称完成。
- 业务备份位于 .local/backups/lima-migration-117/；Lima 专用资产尚待最终清理，其中存在 #116 临时验证容器，已询问其清理范围。
- 未实际调用外部 LLM/Embedding、SMTP 发件；Docling/MinerU 的模型下载和真实 OCR 不在本次验收范围。
