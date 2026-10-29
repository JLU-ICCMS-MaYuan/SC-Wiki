# 实施计划：用户指定上传文件身份

**Issue**：[#179](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/179)
**日期**：2026-10-29
**Spec**：[spec.md](spec.md)

## 摘要与技术上下文

React 19 / TypeScript 5.6 / MUI 7 上传面板使用同一份稳定 fileId 清单，三处文件输入只负责选择区域，不复制上传队列。FastAPI / Python / RQ / Redis 继续接收 main、supplementary、attachment；attachment 的产品名称改为源数据文件。MySQL ScientificUploadDraft 原样持久化任务 JSON，无需迁移。
运行时由 python3 -m scripts.local_deploy.environment 确认为 /Users/mayuan/software/miniconda3/envs/sc-wiki。测试使用 pytest、Vitest、Playwright 隔离 API 浏览器和既有表单契约入口。

## 质量门

| 约束来源 | 要求及满足方式 | 状态 |
| --- | --- | --- |
| Spec / 实施授权 | 用户完整审阅 Spec 后回复“开始 实现”；不再重复申请授权 | 已确认 |
| AGENTS | mayuan 分支逐次核对，显式路径提交，保留其他工作 | 实施期间持续检查 |
| #135 / FR-010 | 仅新任务跳过角色识别；身份一致性检查保留 | 由新旧 Worker / identity 回归验证 |
| #174 | 上传入口有完整 UploadPage 宿主测试；运行规定表单两项检查与影响回归 | 待验证 |
| 数据与授权 | 不操作真实草稿、数据库迁移、部署、push；远程 Spec 链接未推送仍待验证 | 本地边界明确 |

远程链接是关闭门未完成项，不把它伪造为通过；它不改变本次已授权的单 Feature 本地实现范围。

## 文档与源码结构

本目录包含 Spec、Plan、Research、Data Model、Quickstart、Tasks、contracts/upload-files.md 和需求检查表。
源码触点：frontend/src/components/MultiFileUploadPanel.tsx、frontend/src/i18n/{zh,en}/upload.ts；backend/ingest/{upload_contracts,upload_tasks,upload_jobs}.py。沿用 UploadRoleReview 与 resolve-roles 供有界历史任务恢复，不作为新任务入口。验证置于 tests/01_decentralized_uploading/。

## 设计与数据责任

- 浏览器由 MultiFileUploadPanel 的 items 持有唯一选择清单。三个区域使用本地输入、稳定 clientId 及逐文件状态，共用 start 和三并发队列。正文再次选择拒绝并保留原件；错区拒绝，重复与大小规则保留。键盘可操作，窄屏单列。
- upload_contracts 集中检查一个正文、角色与文件格式配对；创建任务前完成校验。新增内部 file_role_policy=user-specified-v1，由服务器写入；不得信任客户端自行指定策略。
- Worker 对此策略校验并直接读取角色；不调用 assess_roles，不改分类，不产生 needs_role_review。引文、来源、结构以及一致性处理继续原路径。
- 没有策略标记的历史任务沿用已部署的角色评估/确认与缓存恢复。没有迁移、回填或按缺字段猜测新策略；不得给历史任务补写新标记。
- 产品继续使用现有 attachment 存储值，避免为改名引入数据库迁移或破坏原证据关系。结构处理和科学记录冲突规则复用既有实现。

## 需求到任务和证据映射

| 需求 / 标准 | 责任与事实来源 | 任务 | 验证 |
| --- | --- | --- | --- |
| FR-001—003 / SC-001 | 上传清单、前后端格式及数量校验 | T002—004 | 新失败先验、完整 UploadPage / API 与 manifest |
| FR-006、007 / SC-002、005 | 服务端策略、Worker 指定 main、统一 sources | T005—006 | 无角色评估调用、四类误导文本、引文/分段文件身份 |
| FR-004、005、008 / SC-003、004 | 原文件、原结构解析及来源定位 | T007 | 纠正值来源、结构真实解析、保存重读既有回归、隔离来源验证 |
| FR-009—011 / SC-006 | 原队列事务及无标记历史入口 | T005—007 | queue/lock/API/历史确认/identity 回归，不写真实业务 |
| FR-012 / SC-007 | 局部状态、完整宿主、清单 | T008—009 | form-contract、mutation、构建、浏览器及范围记录 |

## 阶段与依赖

先完成 T001 文档和一致性核对；US1 测试先失败再实现前后端；US2 在服务端策略建立后接入 Worker；US3 回归既有科学和结构能力；最终浏览器、契约、文档、提交。MVP 为三个区域和用户角色直接生效，全部故事均为本次范围。共享文件串行修改；没有多代理并行任务。

## 必要复杂度

仅新增一个任务策略标记以区分历史数据。删除历史恢复会破坏已有待确认任务；让所有新旧任务永久猜测角色则违反本次需求。复用角色枚举与队列，不新建分类系统或上传框架。
