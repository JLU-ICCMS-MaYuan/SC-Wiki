# 技术研究

## 决策：复用本地编排

理由：现有部署已实现停写、逻辑导出、路径迁移、凭据检查；重写 Mac 数据流程会产生两套规则。备选独立容器已被用户拒绝。证据：scripts/local_deploy/cli.py、runtime.py、storage.py。

## 决策：平台差异集中处理

Mac 缺少 setsid、ss、/proc，系统 Bash 不支持 mapfile。使用 Python 独立会话，Mac 通过 ps/lsof 验证进程和监听者；Linux 保留现有行为。Mac 制品覆盖独立保存，官方 SHA-256 校验，Conda 环境不写 base。实测 dry-run 可解析所需数据库及 Java/Node 包。

## 决策：先保留数据再清理

现有 Lima 数据不是临时缓存。先导出 MySQL、Redis 草稿、Neo4j、Qdrant 及附件，恢复并验证，再删除专用 Lima 实例、下载和构建副本；原始数据包及新备份保留。不会把容器凭据和 Linux 二进制复制成 Mac 运行依赖。

## 兼容边界

Mac 原生开发与 Linux 原生开发共享业务代码。GROBID 的 macOS 动态库和 Java 架构必须实测；OCR 模型下载不作为基础启动隐式动作。历史包源码/迁移不一致需定向迁移，不放宽公共恢复保护。

## 追加研究：Java 21 合并

独立端口实测已证明 GROBID 0.8.1 可以在现有 Java 21.0.9 运行，引用与 PDF 全文解析通过。原 Gradle 7.6.4 不在 Java 21 的受支持运行范围，实测后采用官方 Gradle 8.5；构建和解析均已通过，再更新 Mac 制品覆盖。主环境与 GROBID 共用 JDK，不复制 Conda 包文件。Linux Java 17 路径保持。旧恢复清单需要记录本次定向环境迁移，备份原清单后核对数据库不变；不对任意旧包放宽版本检查。


## Java 21 最终决策与证据

采用 Mac 主环境 Java 21.0.9 与 Gradle 8.5。原有和重新编译的 GROBID 0.8.1 都通过引用、PDF 全文及参考文献解析。官方 0.8.1 的三处 JaCoCo 报告开关使用 Gradle 8 已移除的 enabled 方法，安装器定向转换为 required 属性；不修改业务或解析源码。

构建代码来自官方标签的 Git 对象，逐文件核对对象摘要；模型/原生资源 571 个文件也与同一标签一致。Gradle 镜像下载结果与官方 SHA-256 一致，不关闭 TLS 或跳过摘要。构建产物继续位于 .local/grobid，Java 直接引用 sc-wiki/lib/jvm；Mac 原生库不依赖旧环境的 libxml2/fontconfig，不机械迁移多余包。

当前实例的旧服务清单、环境摘要和部署状态先保存至 .local/backups/java21-consolidation/，确认仅 GROBID 工具链改变、数据库清单不变后更新归属元数据；旧冻结归档保持原样。公共部署逻辑仍拒绝未知版本、来源及不匹配的数据包。
