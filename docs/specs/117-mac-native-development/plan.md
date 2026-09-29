# 实施计划：Mac 原生本地开发

**GitHub Issue**：[#117](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/117) · **日期**：2026-09-29 · **Spec**：[spec.md](spec.md)

## 摘要与技术上下文

GNU Make、系统 Bash 3.2、Python 3.12；Conda 管理 MySQL 8.4.2、Redis 8.10.1、Java 21 与 Node 22。项目私有 Go 1.25.14、Qdrant 1.19.0、Neo4j 5.26.29、GROBID 0.8.1；Mac 共用 Java 21/Gradle 8.5，Linux 保留 Java 17。目标为当前 macOS arm64，保留 Linux x86_64。复用 scripts/local_deploy 的配置、状态、存储、冻结与恢复职责，不复制业务逻辑。

## 质量门

| 来源 | 要求 | 方案 | 状态 |
| --- | --- | --- | --- |
| AGENTS.md | mayuan 分支、隔离其他改动、自动提交 | 每次修改检查分支，仅明确路径暂存 | 通过 |
| FR-001/002 | 原生源码运行，Linux 兼容 | 独立 Makefile.mac，公共流程通过小型平台适配 | 通过 |
| FR-003/004 | 本地环境及安全恢复 | 官方制品摘要、既有状态和存储门槛 | 通过 |
| FR-005 | 数据先迁移后清理 | 最新逻辑备份和恢复核对，最后删除 Lima | 通过 |

## 源代码结构

- Makefile / Makefile.mac：按系统选择入口和 Mac 配置。
- scripts/local_deploy/environment.py、native.py：选择 Mac 制品和验证安装。
- scripts/local_deploy/runtime.py、平台辅助模块：进程归属与端口检查。
- scripts/lib-local.sh、dev.sh：兼容系统 Bash，跨平台进程会话及服务配置。
- scripts/local-deploy-macos.json：Mac 制品覆盖；保留 Linux 清单。
- tests/02_maintenance_and_verification/：跨平台命令、归属、安装与恢复边界回归。

## 需求到设计的映射

| 来源 | 组件及数据来源 | 任务 | 验证 |
| --- | --- | --- | --- |
| FR-001/002 / SC-001 | Makefile、dev.sh、工作区源码 | T002/T003 | 路由、真实启停及重载 |
| FR-003 | environment/native、官方发布清单 | T002/T003 | 摘要及可执行文件版本 |
| FR-004 / SC-002 | cli/state/storage、原有数据包契约 | T002/T004 | 只读预检、真实冻结恢复 |
| FR-005 / SC-003 | 旧实例导出及原生恢复 | T005 | 数量/附件摘要、目录检查 |
| FR-006 / SC-004 | 文档及 Git 范围 | T006 | 回归、链接和暂存审查 |

## 阶段与依赖

T001 → T002 → T003 → T004 → T005 → T006。数据清理必须等待恢复核验；不使用并行代理，不覆盖 #116 的在途修改。

## 复杂度说明

只对平台不同的进程检查、制品和本地动态库作适配；数据包仍沿用既有严格版本兼容，不承诺任意历史包跨平台直接恢复。现有 dist 历史包通过本次定向迁移保留，不绕过常规 deploy 检查。

## Java 21 合并增量计划

FR-007/SC-005 → T007～T009。Mac 的 GROBID 配置由版本清单声明 Java 环境来源，安装器复用显式传入的主环境前缀；启动脚本读取同一配置。使用官方 Gradle 8.5，适配上游 build.gradle 的三处报告 enabled→required 语法，验证 Java 21 构建，避免运行与重建条件分离。真实重建产物通过解析验收后替换旧制品，保存旧部署元数据到私密备份；定向更新当前实例的清单、源码摘要和环境摘要，不修改数据库。停止旧 GROBID 后切到共享 JDK，最后删除旧 Java17、下载及构建临时文件。
