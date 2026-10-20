# 实施与验收记录

对应 [Issue #142](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/142)。本次完成源码、隔离验收和文档；未迁移业务库、部署或推送。远程 Spec 链接待推送后核验，因此 Issue 保持开放。

## 验证结果

| 验证 | 结果与边界 | 证据 |
| --- | --- | --- |
| Go 全量 | `go test ./...` 通过；常规运行中显式要求隔离库的用例跳过，随后在集成脚本中实际执行 | [日志](assets/go-tests.txt) |
| Python 与部署 | 60 通过、23 按原有环境条件跳过；包含新增 9 项选题、引用及配置边界测试 | [日志](assets/python-tests.txt) |
| 前端 | 社区、排行榜/图表、新闻及侧栏共 52 项通过 | [日志](assets/frontend-tests.txt) |
| 生产构建 | TypeScript 与 Vite 构建通过；沿用现有 3Dmol eval 和大包提示 | [日志](assets/build.txt) |
| 真实 MySQL/Redis | 新增迁移升级→降级→升级；有 AI 内容时拒绝破坏性降级；隔离库自动清理 | [集成日志](assets/integration.txt) |
| 模型任务 | 两个真实本机 HTTP 上游、真实 RQ 消费，验证共享资料、各自凭据、部分失败与重试、并发完成、任务重放、终态凭据清理 | [集成日志](assets/integration.txt) |
| 冲突与恢复 | 真实 HTTP 请求期间并发人工修订；下架保护、引用撤回；启动正式双消费者命令，在请求期间杀掉该测试进程及后代，推进隔离超时时钟后验证失败恢复 | [集成日志](assets/integration.txt) |
| 浏览器 | 实际 Go/Python AI 路由及生产构建，访客/user/admin/superadmin 四身份，桌面和 390px 窄屏、中文/英文；6 组检查通过，脚本错误 0 | [检查](assets/browser.json) |

浏览器使用一次性测试账号和论文，模型选择菜单返回隔离目录夹具。站内检索传输使用固定公开片段；数据库批准状态、版本、引用、任务及发布检查走真实代码。未调用真实商业模型供应商，没有科学准确性或目标环境 Qdrant/Embedding 端到端验收结论。

## 关键修复与实现依据

- 真实启动测试发现 `__main__` 内消费者无法被 spawn 反序列化，消费者移入 `backend.community.worker`。
- macOS fork work horse 触发 Objective-C 崩溃，macOS 改用 RQ SpawnWorker；Linux 保持常规 Worker。没有通过关闭系统 fork 安全检查绕过故障。
- 模型完成后另开事务汇总批次，避免跨模型反向锁等待及旧快照；并发完成与重复执行已经验证。
- 保存模型阅读过的全部资料依赖，公开页面只列实际引用；未显式引用的输入资料撤回后，同样不继续公开基于该资料生成的正文。
- 问题准备失败可从详情的模型状态重试对应批次；答案失败只重试该模型。无网络搜索接口。

## 可复查命令

在已加载项目环境变量的开发环境运行：

```bash
(cd goserver && go test ./...)
python -m pytest -q backend/tests/test_community_generation.py tests/02_maintenance_and_verification/test_local_deployment.py tests/02_maintenance_and_verification/test_local_environment.py tests/07_researcher_community_forum/test_news_compose.py
node frontend/node_modules/vitest/vitest.mjs run --config vitest.config.ts tests/07_researcher_community_forum tests/02_identity_governance/sidebar-navigation.test.tsx
npm --prefix frontend run build
python tests/07_researcher_community_forum/verify-ai-community.py --browser
```

最后一条需要本机 MySQL 创建隔离测试库的权限、Redis 可执行文件，并设置 `PLAYWRIGHT_MODULE` 和 `CHROMIUM_PATH`。脚本从 `.env` 只读获取 MySQL 连接配置，仅创建/删除自身随机命名的 `scwiki_issue142_test_*` 数据库；使用随机端口的新 Redis，不清理或迁移业务库。所有模型 HTTP 请求均发到脚本创建的本机夹具。

## 界面证据

![访客桌面只读](assets/guest-desktop.png)

![超级管理员窄屏](assets/superadmin-mobile.png)

## 交付边界

- 本地源码验证完成，不代表业务环境已启用。新功能需要配套迁移、Go/Python/前端版本和 community-worker。
- README、社区 Overview、迁移头与结构清单、Docker 和本地启动配置已同步。
- 当前已有其他任务的未提交修改，仅提交本任务文件及 README 对应段落。
- Issue/Spec 双向远程链接未验证，不自动推送或关闭 Issue。

## 独立提交候选复验

从暂存索引导出独立代码目录，未复制其他任务的未提交改动；新增 Python 9 项测试与前端生产构建再次通过。README 索引只包含社区段落，原有上传修改留在工作区。

## 本地运行反馈：历史问题读取恢复

用户反馈见 IMG-001/IMG-002。实际连接 `127.0.0.1:3307/scwiki`，迁移版本仍为 `20261015_0094`，没有 AI 表和 `model_order` 字段；Go 日志与实际请求均确认 `ORDER BY model_order` 导致 1054/500。

修复历史问题的排序选择：没有模型任务时请求 `sort=latest`，有模型任务时仍使用 `sort=models`。13 项社区前端测试与生产构建通过；实际 `http://127.0.0.1:5173/share/discussions/7` 在无登录的浏览器中恢复 200 和“暂无内容”，没有发帖或触发 AI。见 [实际只读核验](assets/runtime-read-check.json) 与 [恢复截图](assets/runtime-read-fixed.png)。

同时核实：社区 Worker 未运行、队列为空，Python API 因热重载停在连接关闭等待；`mayuan` 是普通账号，`superadmin_mayuan` 是正常且邮箱已验证的超级管理员。没有改变任何账号角色。旧问题不会自动补答，生成需要新的超级管理员提问。

已对六张现有社区表及 Alembic 版本表做只读备份，并生成从 0094 到 0142 的离线迁移 SQL。备份位于 `.local/backups/community142-20261020-190219/`，包含 SHA-256 清单；现有社区数据为一个问题，其余社区表为空。备份和迁移清单不入 Git。尚未执行业务库迁移或服务启用，等待用户明确授权。

## 本地部署完成

本轮用户明确要求“你来帮我确认，然后完成部署这个讨论部分”，授权范围为本机实例；不是远程服务器部署。

- 执行前确认迁移头 0094、活动事务 0、上传队列及社区队列均空；已有备份与 SQL 哈希通过复核。
- 本机 `127.0.0.1:3307/scwiki` 已应用 `20261020_0142`。六张原社区表逐字段比对一致，新批次/任务/修订表为空；没有修改账号角色或给历史问题自动补答。见 [迁移结果](assets/local-migration.json)。
- 恢复卡在热重载关闭等待的 Python API；正常启动两个社区消费者。健康、公开问题、Vite 模型排序读取均返回 200；普通账号调用管理接口 403，超级管理员 200。见 [API 核验](assets/local-api-check.json)。
- 正式社区 Worker 实际消费了一次只读站内检索检查任务，结果为空；测试任务已经清理，没有新增讨论内容。见 [Worker 核验](assets/local-worker-check.json)。
- 当前没有已公开论文，也没有 Embedding 密钥。修复空库处理后，数据库确认无资料时可使用通用知识；将来公开文献检索需要配置可用 Embedding/向量服务，检索故障不会被隐藏为空结果。
- 实测 GPT 网关对普通请求返回 text/event-stream，旧非流式代码收到字符串而无法取 choices。复用项目原有流式 JSON 接口后，deepseek-v4-pro 和 gpt-6-sol 都实际完成回答，约 6.6 秒与 11.3 秒；没有使用隔离模型夹具替代本次真实调用，也没有发布测试答案。见 [真实模型核验](assets/local-model-check.json)。
- 补充空库及截断流检查后，11 项单元测试通过；更新 HTTP SSE 夹具的真实 MySQL/Redis/RQ 回归（含实际进程中断）通过。见 [回归日志](assets/deployment-regression.txt)。
- 实际浏览器确认普通用户没有提问按钮，超级管理员可见手动提问、AI 随机提问和任务入口，没有服务报错。见 [页面核验](assets/local-browser-ready.json) 与 [截图](assets/local-superadmin-ready.png)。

运行环境是本机热加载工作区，其中包含其他任务未提交代码；本次提交只纳入社区增量，不将整个运行环境冒称独立干净制品。未推送，也未部署其他机器。此前“未迁移”的记录是当时状态，本节为本轮最新结果。
