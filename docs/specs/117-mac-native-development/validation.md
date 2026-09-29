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

## 收尾验收（已完成）

- make frozen 的未提交源码拒绝门槛已验证。实现提交后真实生成 .local/backups/scwiki-macos-117.tar.gz（约 7.8 MB，73 个载荷文件），完整摘要校验通过，源应用服务自动恢复。初次实测发现 ps/lsof 之间进程退出的竞态，b437dbc 修复后原生专项 12 通过、1 跳过，真实冻结重试成功。
- 使用 Git 提交源码的独立目录和全新配置，真实运行 make deploy 恢复该冻结包；54 表/3595 行、图谱和向量配置一致，恢复 1 条有效草稿。验证目录服务全部停止后切回原实例，再删除验证目录。没有绕过部署版本、归属、数据完整性或凭据保护。
- 业务备份位于 .local/backups/lima-migration-117/，删除旧环境前再次核对全部备份摘要。检查发现 #116 临时容器已被其任务清理，旧 VM 不再被其他任务占用；因此按用户原授权删除专用 scwiki 虚拟机、~/.scwiki-lima/、.local/mac-deploy/、.local/scwiki-runtime/，并清理已结束的验证副本、归档和本次一次性脚本。
- 清理后 make status 显示 11 个原生服务运行；主页及核心 API 正常，代码已本地提交且未推送。旧 Linux 包与业务备份保留；原子移动/导出/恢复过程中未清空业务数据。
- 未实际调用外部 LLM/Embedding、SMTP 发件；Docling/MinerU 的模型下载和真实 OCR 不在本次验收范围。

## 证据位置

本机 .local/mac-native-verification.json、mac-pdf-smoke-report.json、mac-reload-verification.json、mac-roundtrip-verification.json、mac-cleanup-verification.json 保留汇总证据。备份说明在 .local/backups/README.md；这些运行产物与凭据均不进入 Git。

Issue #117 已记录本地交付结果；由于未获推送授权，代码与 Spec 尚未发布到远端，Issue 保持开放供后续审阅，不将本地完成混写成服务器部署完成。


## Java 21 环境合并验收

2026-09-29 追加：Mac GROBID 已改为与 Neo4j 共用 sc-wiki 的 Java 21.0.9；Linux Java 17 配置未变。

- 原有 GROBID 0.8.1 在独立端口使用 Java21 启动、引用/PDF 解析通过。
- 使用官方 0.8.1 标签构建源码（763 个所需文件按 Git 对象摘要核对）和 571 个已核对的模型/原生资源，采用 Gradle 8.5、Java21 完整执行 distZip 成功。Gradle 制品 SHA-256 与官方一致。
- 上游 build.gradle 的 xml/html/csv 三处报告 enabled 开关不兼容 Gradle8；安装器定向改为 required，解析源码不变。新产物在独立端口通过引用、PDF 全文和参考文献提取。
- 已切换正常 GROBID 服务至新产物，实际 Java 可执行文件为 sc-wiki/lib/jvm/bin/java。通过 Conda 移除旧 .local/grobid-java 后，再次重启、解析和 make deploy 均成功。
- 定向回归 96 通过、24 跳过；覆盖不创建重复环境、主环境缺失、版本不符、Gradle 配置适配和 Linux 原清单保持。跳过项仍为此前明确的隔离环境或平台条件，不计为通过。
- 定向迁移只更新当前实例的 GROBID 工具链、环境摘要和源码摘要；原元数据备份至 .local/backups/java21-consolidation/。数据库结构/行数清单保持一致，其他服务清单不变，历史冻结包原样保留。
- 独立 Java17 约 362 MB 已释放；本次源码、构建工具、缓存、下载文件和旧 GROBID 制品副本均已删除。未向主 Conda 环境复制不需要的 libxml2/fontconfig 文件，也未修改系统 Java 或 Conda base。
- 本机汇总证据：.local/java21-consolidation-verification.json。外部 LLM、SMTP、真实 OCR 和生产镜像未新增验收。
