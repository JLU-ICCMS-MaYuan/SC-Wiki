# 技术研究

## 决策：复用本地编排

理由：现有部署已实现停写、逻辑导出、路径迁移、凭据检查；重写 Mac 数据流程会产生两套规则。备选独立容器已被用户拒绝。证据：scripts/local_deploy/cli.py、runtime.py、storage.py。

## 决策：平台差异集中处理

Mac 缺少 setsid、ss、/proc，系统 Bash 不支持 mapfile。使用 Python 独立会话，Mac 通过 ps/lsof 验证进程和监听者；Linux 保留现有行为。Mac 制品覆盖独立保存，官方 SHA-256 校验，Conda 环境不写 base。实测 dry-run 可解析所需数据库及 Java/Node 包。

## 决策：先保留数据再清理

现有 Lima 数据不是临时缓存。先导出 MySQL、Redis 草稿、Neo4j、Qdrant 及附件，恢复并验证，再删除专用 Lima 实例、下载和构建副本；原始数据包及新备份保留。不会把容器凭据和 Linux 二进制复制成 Mac 运行依赖。

## 兼容边界

Mac 原生开发与 Linux 原生开发共享业务代码。GROBID 的 macOS 动态库和 Java 架构必须实测；OCR 模型下载不作为基础启动隐式动作。历史包源码/迁移不一致需定向迁移，不放宽公共恢复保护。
