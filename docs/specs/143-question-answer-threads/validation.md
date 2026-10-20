# 验收与本地启用

对应 [Issue #143](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/143)。用户已批准完整计划及本地启用；不推送、不部署其他机器。

## 验证结果

| 项目 | 实际结果 | 证据 |
| --- | --- | --- |
| Go 全量 | go test ./... 通过，社区当前读写权限保持 | [日志](assets/go-tests.txt) |
| Python | 13 项通过，包含完整前文、不明回应标识、重复后续答案拒绝及空库处理 | [日志](assets/python-tests.txt) |
| 前端 | 社区及侧栏 54 项通过；问题内选模型、运行时继续入队及同卡追加覆盖 | [日志](assets/frontend-tests.txt) |
| 构建 | TypeScript/Vite 通过，现有大包和 3Dmol eval 警告未改变 | [日志](assets/build.txt) |
| 集成 | 真实隔离 MySQL/Redis/RQ/HTTP SSE：A→B→A 两卡三段、完整上下文、幂等、失败继续、队尾重试、修订冲突、来源/隐藏保护、随机题不自动回答通过 | [日志](assets/integration.txt) |
| 进程恢复 | 正式 Worker 在 HTTP 生成期间被终止，推进隔离超时时钟后恢复失败状态，重试排队尾并成功 | [日志](assets/integration.txt) |
| 浏览器 | 四身份、桌面/390px窄屏/英文，模型分卡、补充段、真实入队弹窗均通过，脚本错误0 | [结果](assets/browser.json) |
| 真实模型 | DeepSeek→OpenAI→DeepSeek 实际调用，后两次传入完整前文并回应；测试内容未发布 | [回答记录](assets/live-model-sequence.json) |

集成检索片段为固定夹具，论文批准版本、前文采集、引用校验、存储和队列使用真实代码。实际模型测试不使用夹具，也不写公开内容。模型样例是回应机制验收，不是科学结论审定。

## 真实模型发现与修复

第一轮 DeepSeek 第三次回答重复首答。增加当前模型/追加轮次提示、必须回应前文标识及完全重复检测；不合格时只纠正重试一次，仍不合格标为 answer_not_distinct，不能发布。

复验中 OpenAI 明确认同并修正首答的判据表述；DeepSeek 第三次明确引用 A1/A2、承认前述修正并补充另一个分析角度。没有为了分歧强制模型选择反对立场。生成质量仍受模型能力约束。

## 本地迁移与服务

- 切换前确认旧批次/任务活动数及社区队列均为0，先停止社区 Worker。
- 备份 `.local/backups/community143-20261020-200908/` 包含原社区表 SQL、逐行快照与哈希。指定从142升级143，未应用其他任务未提交的0049分支。
- 原社区表逐字段比对一致，已有4条内容保留；回填2张模型卡映射，未新增公开答案。见 [迁移核验](assets/local-migration.json)。
- 两消费者已恢复；实际队列只读目录探针通过。普通用户/管理员无生成权限，超级管理员模型目录与题内队列200。见 [API核验](assets/local-api.json)。
- 当前5173页面实测显示DeepSeek/OpenAI分卡、模型选择弹窗、窄屏无溢出；无发布测试写入。见 [页面核验](assets/local-browser.json)。
- 部署为现有热加载工作区，含其他任务未提交内容；本次Git只收社区增量，不把整体运行工作区冒称干净提交制品。

## 命令

```bash
(cd goserver && go test ./...)
python -m pytest -q backend/tests/test_community_generation.py
node frontend/node_modules/vitest/vitest.mjs run --config vitest.config.ts tests/07_researcher_community_forum tests/02_identity_governance/sidebar-navigation.test.tsx
npm --prefix frontend run build
python tests/07_researcher_community_forum/verify-answer-threads.py --browser
```

最后一条要求项目环境、隔离MySQL建库权限、Redis程序，以及 PLAYWRIGHT_MODULE/CHROMIUM_PATH；只删除自身创建的 scwiki_issue143_test_* 库。旧 verify-ai-community.py 转为本验收入口，避免继续要求已退役的自动全模型回答。

## 界面

![实际模型答案卡](assets/local-desktop.png)

![选择模型](assets/local-model-dialog.png)

## 边界

没有联网、自动评分、用户发言或自动批量补答。旧首答保留原内容和时间；新排队与追加显式使用UTC时间避免数据库时区差异。远程Spec链接待推送后验证，Issue保持开放，不自动推送。

## 同时进行的其他任务

提交前发现 #49 已由另一任务提交并独立部署；部署清单保留其0049分支并追加143，不将已完成的0049分支删除。两条迁移均从142分出，本任务没有执行0049迁移。

独立暂存候选（不复制其他任务未提交修改）再次通过13项Python测试与前端生产构建。最终本机迁移头为0049与0143：0049由另一任务独立部署，本任务仅执行0143。

## 紧凑布局、多选和独立答案页

用户认可Demo并追加“单击某个答案，可以调整到另一个独立的页面里”，本轮实现FR-012–015、SC-005–006。

- 问题页最大680px，各答案默认仅显示模型身份、两行摘要和回答次数，点击原生链接进入 `/share/discussions/:id/answers/:answerId`。独立页完整显示该模型首答/补充、来源及管理操作；可刷新、返回问题，前文引用跳转另一答案页具体分段。
- 生成按钮旁直接多选模型，默认选择当前可用模型；勾选顺序决定入队顺序，空选禁用，无选择弹窗。
- 新增批量幂等组表，全部模型和卡片状态先校验，再单事务保存组与子任务，Redis凭据写入失败则回滚并清理本次键。同UUID同参数复用、异顺序409；客户端提交失败保留同UUID重试。原单模型接口复用同一实现。
- 独立答案API同时校验父问题、答案类型与原有可见性；错父问题或隐藏祖先404，普通账号保持只读。

### 验收证据

| 验证 | 结果 | 证据 |
| --- | --- | --- |
| Go全量 | 通过，新增独立答案父子匹配/隐藏祖先测试 | [日志](assets/compact-live/go-tests.txt) |
| Python | 13项通过，原生成、引用和完整前文规则无回退 | [日志](assets/compact-live/python-tests.txt) |
| 前端 | 社区及侧栏57项通过，包含多选顺序、空选、UUID重试及独立页 | [日志](assets/compact-live/frontend-tests.txt) |
| 构建 | TypeScript/Vite通过，已有大包/3Dmol警告不变 | [日志](assets/compact-live/build.txt) |
| 真实MySQL/Redis/RQ/HTTP模型 | 原子批量、并发幂等、无效模型、第二次凭据写入失败回滚、单模型生成失败后继续，及此前完整队列/恢复场景通过 | [日志](assets/compact-live/integration.txt) |
| 隔离浏览器 | 四身份，真实批量接口按OpenAI→DeepSeek入队；680px摘要、独立页直达/刷新、跨答案定位、返回、390px及英文通过；脚本错误0 | [结果](assets/compact-live/isolated-browser.json) |
| 本机浏览器/API | mayuan只读、superadmin_mayuan行内多选；真实既有答案独立页与返回通过，无弹窗、空选禁用、窄屏无溢出；没有POST生成测试数据 | [浏览器](assets/compact-live/browser.json)、[API](assets/compact-live/api.json) |

### 本地部署

本机迁移由0049+0143变为0049+0143b；仅新增community_answer_groups。原13张社区表全部逐字段不变，包含4条问题/答案、2张模型卡。备份位置及SHA-256见 [迁移核验](assets/compact-live/migration.json)。旧队列为空时停社区Worker，迁移后恢复两个真实消费者，读取目录的只读RQ探针通过；Redis旧Worker注册项可能短暂残留，按本机当前进程组验证两活进程，不把过期注册项当作运行进程。

未更改账号权限，未修改既有答案，未触发正式生成测试，未部署其他机器或推送。真实模型内容生成规则沿用上一轮已经实测的链路，本轮外部模型使用隔离HTTP/SSE验证批量及上下文，不把它称为新一轮科学准确性检验。

![本机紧凑摘要与行内多选](assets/compact-live/superadmin-summary.png)

![本机独立答案页](assets/compact-live/superadmin-detail.png)

本轮独立暂存候选（不复制其他任务的未提交修改）再次通过13项Python测试与前端生产构建。
