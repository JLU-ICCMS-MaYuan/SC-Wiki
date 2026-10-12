# 实施任务：RAG 对话工作区

**输入**：[spec.md](spec.md)、[plan.md](plan.md)、[research.md](research.md)、[data-model.md](data-model.md)、[接口契约](contracts/rag-chat.md)

2026-10-09 原工作区代码、文档和本地验证已完成；目标环境验收仍见 T018。2026-10-12 润色增强代码与本地自动化验证已完成，真实模型结果待人工质量复核，登录浏览器完整链路待完成，见阶段 6。T010～T013 的勾选只代表旧版预览交互，不能证明修订后的 US3 已完成。任务编号用于技术拆解，协作状态以 [Issue #125](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/125) 为准。

## 阶段 1：基础能力

**目的**：让云端会话具备受保护的主库事实来源，再接入页面。

- [x] T001 [US2] 在 `backend/tests/test_rag_chat_conversations.py` 先写主库事务、账号隔离、导入幂等、轮次原子提交和跨设备冲突测试，对应 FR-005～FR-009、SC-002。
- [x] T002 [US2] 在 `backend/models.py` 与 `alembic/versions/20261009_0125_rag_chat_conversations.py` 增加主库会话和完成轮次及约束，对应 FR-005、FR-006、FR-009。
- [x] T003 [US2] 在 `backend/services/rag_chat_conversations.py` 实现所有权校验、分页列表、删除、显式导入、请求幂等和序列检查，对应 FR-005～FR-009。
- [x] T004 [US2] 在 `backend/api/rag.py` 扩展会话 API 与 `/chat/stream` 云端模式，完成后先提交轮次再发送 `done`，保留访客旧请求契约，对应 FR-005～FR-009。

## 阶段 2：US1 与 US2——对话布局和历史（P1）

**目标**：用户进入页面即可提问，并清楚区分本机历史与云端历史。

**独立验收**：`quickstart.md` 的布局、本机与云端、账号隔离、失败与并发场景通过。

- [x] T005 [US1] 在 `frontend/src/pages/RagPage.test.tsx` 先写空态、历史切换、窄屏导航、云端同步标识与旧历史显式导入测试，对应 FR-001～FR-003、FR-005、FR-007、FR-008、SC-001、SC-002。
- [x] T006 [US2] 在 `frontend/src/lib/ragConversations.ts` 封装云端会话、导入和失败状态请求，对应 FR-005～FR-009。
- [x] T007 [US2] 在 `frontend/src/lib/useStreamingChat.ts` 区分访客本机与登录云端状态，处理流式完成、重试、切换账号和导入旧历史，对应 FR-005～FR-009。
- [x] T008 [US1] 在 `frontend/src/pages/RagPage.tsx` 改为左侧历史、中央对话及底部多行输入布局，移除常驻证据栏并保留探索模式，对应 FR-001～FR-004、SC-001、SC-005。
- [x] T009 [US1] 在 `frontend/src/i18n/zh/rag.ts` 与 `frontend/src/i18n/en/rag.ts` 增加历史、同步、错误和键盘辅助文案，对应 FR-017。

## 阶段 3：US3——星形润色（P1，旧版实施记录）

**目标**：用户能安全预览 AI 改写并自行选择是否采用。

**独立验收（历史）**：2026-10-09 的空草稿、接受、取消、失败和编辑竞态通过；当前目标已由阶段 6 替代。

- [x] T010 [US3] 在 `backend/tests/test_rag_chat_conversations.py` 先写空草稿、模型错误、输出边界、保留科学符号和不创建问答轮次的测试，对应 FR-010、FR-011、SC-003。
- [x] T011 [US3] 在 `backend/api/rag.py` 与 `backend/rag/service.py` 增加独立润色接口，复用请求级模型配置，对应 FR-010、FR-011。
- [x] T012 [US3] 在 `frontend/src/pages/RagPage.test.tsx` 先写预览、接受、取消、失败及编辑竞态测试，对应 FR-010～FR-012、SC-003。
- [x] T013 [US3] 在 `frontend/src/pages/RagPage.tsx` 实现输入框星形按钮与候选预览，接受后仅替换当前草稿，对应 FR-002、FR-010～FR-012。

## 阶段 4：US4——回答内来源与临时详情（P1）

**目标**：点击真实来源后临时查阅文献，不占据默认布局。

**独立验收**：`quickstart.md` 的已批准、无匹配、旧版本和关闭恢复场景通过。

- [x] T014 [US4] 在 `backend/tests/test_rag_chat_links.py` 先写已批准论文、物性定义、重名、无匹配、撤回和旧版片段验证，对应 FR-013～FR-015、SC-004。
- [x] T015 [US4] 在 `backend/rag/search/sql_search.py` 与 `backend/api/rag.py` 增加有界来源解析和当前版本片段读取，复用已批准论文过滤，对应 FR-013～FR-015。
- [x] T016 [US4] 在 `frontend/src/pages/RagPage.test.tsx` 先写引文/关键词点击、Drawer 关闭与焦点恢复测试，对应 FR-013～FR-016、SC-004。
- [x] T017 [US4] 在 `frontend/src/components/MarkdownMessage.tsx`、`frontend/src/components/RagSourceDrawer.tsx` 和 `frontend/src/pages/RagPage.tsx` 实现可验证链接、右侧按需详情与关闭恢复，对应 FR-004、FR-013～FR-016。

## 阶段 5：收尾与回归

- [ ] T018 在 `backend/tests/test_rag_chat_conversations.py`、`backend/tests/test_rag_chat_links.py`、`frontend/src/pages/RagPage.test.tsx` 和 `docs/specs/125-rag-chat-workspace/quickstart.md` 运行并记录跨账号、跨浏览器、模型失败、来源版本与原有探索模式回归，对应 SC-001～SC-005。
- [x] T019 根据已实现代码与本地验证使用 `big-project-overview-maintainer` 更新 `docs/overview/05_Retrieval-Augmented_AI_Question_Answering/streaming-qa-and-evidence.md`；更新 `README.md` 的问答使用说明，并完成 Issue #125 的 Documentation Impact。

## 依赖与执行顺序

- T001 → T002 → T003 → T004 是云端主路径；同一文件上的任务按编号串行。
- T005 可在后端基础能力建设时准备；T006 → T007 → T008 → T009 后验收 US1/US2。
- T010 → T011、T012 → T013 是润色后端与前端链路；T013 接受布局 T008 的输入区。
- T014 → T015、T016 → T017 是来源后端与前端链路；T017 接受布局 T008 的消息区。
- T018 依赖全部功能任务，目标环境验收仍待完成；T019 基于已实现代码和本地验证回写当前行为，未把环境验收写成已完成。

## 需求覆盖

| 来源 | 任务 | 验收依据 |
| --- | --- | --- |
| US1、FR-001～FR-004、SC-001 | T005、T008、T017、T018 | 默认无右栏，桌面/窄屏、流式与探索模式 |
| US2、FR-005～FR-009、SC-002 | T001～T007、T018 | 主库恢复、账号隔离、显式导入、失败并发 |
| US3、FR-010～FR-012、SC-003 | T010～T013（历史）；T021～T025、T027（当前） | 直接回填、撤销、失败和上下文竞态；旧测试不能证明新目标 |
| US3、FR-018、SC-006 | T020、T022、T023、T026 | 有来源模板、适度完善提问、真实质量对比 |
| US3、FR-019、SC-003 | T024、T025、T027 | 逐字撤销、后续编辑及上下文变化使撤销失效 |
| US3、FR-020～FR-021、SC-007 | T021、T023、T026、T027 | 输出完整且可发送，单独润色不创建历史 |
| US4、FR-013～FR-016、SC-004 | T014～T018 | 来源验证、当前版本、临时详情、焦点 |
| FR-017、SC-005 | T008、T009、T018、T024、T025、T027、T028 | 中英文、键盘、普通问答、探索与模型回归 |

## MVP 与增量策略

1. 完成云端基础能力与 US1/US2，可独立交付清爽布局和跨设备历史。
2. 加入 US3 的独立草稿润色，不改变问答持久化契约。
3. 加入 US4 的来源链接与按需详情，再执行完整回归和文档回写。

## 阶段 6：US3——提示词完善与直接回填（2026-10-12 增量）

**目标**：在原工作区上增强提问质量，直接回填且可撤销，不重做云端会话或来源功能。

**独立验收**：[质量评测](prompt-polish-evaluation.md)及[验证指南](quickstart.md)中的新版润色场景通过，真实模型与交互证据分开记录。本阶段代码任务已完成；真实调用不等于人工质量门通过，未满足的验收任务仍保持未勾选。

- [x] T020 [US3] 在 `docs/specs/125-rag-chat-workspace/prompt-polish-evaluation.md` 核对并冻结 12 条输入、评分标准、旧版代码/模板快照与实际模型信息，后续输出记录到本目录 `prompt-polish-results.md`，对应 FR-018、SC-006。
- [x] T021 [US3] 在 `backend/tests/test_rag_chat_conversations.py` 补充真实路由到服务的润色测试，只替换外部模型边界：覆盖空白、1000/1001 字符、完整结束/截断/缺失标记、空正文、公式/数值/单位/占位符、凭据与超时、无会话写入；失败结果不得返回成功，对应 FR-010、FR-011、FR-020、FR-021、SC-007。
- [x] T022 [US3] 在 `backend/rag/prompts/prompt_polish.md` 移植并适配固定上游模板，在 `backend/rag/prompts/prompt_polish.LICENSE` 保留 MIT 版权和许可全文；记录提交、路径及适配说明，覆盖模糊问题完善、简单问题轻改写、禁止虚构条件与保持输入语言，对应 FR-018、SC-006。
- [x] T023 [US3] 在 `backend/rag/service.py` 和 `backend/api/rag.py` 接入模板与序列化草稿，统一 1000 字符边界、4096 tokens 生成额度、完整结束和关键内容校验，沿用模型选择与错误映射；运行 T021 测试并验证生产打包可读取模板，对应 FR-010、FR-011、FR-018、FR-020、FR-021、SC-007。
- [x] T024 [US3] 在 `frontend/src/pages/RagPage.test.tsx` 将旧预览测试更新为直接回填、零自动发送、撤销逐字恢复/失效、失败非阻塞、编辑后改回原文、发送及失败恢复、空会话再次新建、会话切出再切回、账号变化、卸载和重复点击的回归测试，对应 FR-010～FR-012、FR-017、FR-019、SC-003。
- [x] T025 [US3] 在 `frontend/src/pages/RagPage.tsx` 移除候选确认弹窗，增加请求/草稿/上下文保护、自动回填和一次撤销，必要时在 `frontend/src/lib/useStreamingChat.ts` 暴露最小上下文变化信号；更新 `frontend/src/i18n/zh/rag.ts` 与 `frontend/src/i18n/en/rag.ts` 文案并运行 T024，对应 FR-010～FR-012、FR-017、FR-019、SC-003。
- [ ] T026 [US3] 按 `docs/specs/125-rag-chat-workspace/prompt-polish-evaluation.md` 用同一真实模型运行旧/新各两轮，向本目录 `prompt-polish-results.md` 写入脱敏原始结果、人工评分、有效性、延迟、用量及结论；不足 80% 改善或任何硬约束违规时修订模板并重跑完整集合，对应 FR-018、FR-020、SC-006、SC-007。
- [ ] T027 [US3] 在 `docs/specs/125-rag-chat-workspace/quickstart.md` 记录后端专项、前端测试/构建、桌面与窄屏真实浏览器的回填→撤销→再次润色→主动发送、上下文竞态、模型失败及普通/探索模式回归；确认前后端运行制品对应已验证源码，对应 SC-003、SC-005、SC-007。
- [ ] T028 [US3] 完成实现和验证后使用 `big-project-overview-maintainer` 更新 `docs/overview/05_Retrieval-Augmented_AI_Question_Answering/streaming-qa-and-evidence.md` 与 `availability-and-configuration.md`，同步 `README.md` 及本目录实际验证状态；通过 Issue skill 同步 #125 的文档影响与验收证据，保留未完成的 T018，对应 FR-017～FR-021、SC-003、SC-005～SC-007。

### 增量依赖与交付门

- T020 → T021 → T022 → T023 为后端与质量基线；T024 → T025 为前端测试与实现。
- T026 依赖 T020、T023；T027 依赖 T023、T025、T026；T028 依赖 T027。
- 前后端独立文件可分开处理，同一文件串行；本规划没有要求并行代理。
- T020～T028 不修改旧任务编号与历史勾选含义。只有 T026 有真实质量证据、T027 有完整交互证据，才能声称新版润色验收通过。
- #125 最终关闭同时依赖原 T018、当前 T020～T028 和 Documentation Impact；不能以本轮规划完成替代功能完成。


### 2026-10-12 验证范围

- T020～T025 已完成：固定基线与模型配置、有来源模板、实际润色路径、前端直接回填和一次撤销。后端专项 47 项、前端 26 项及生产构建通过。
- T026 已执行真实 DeepSeek 新旧对比并保留原始输出；人工盲评与 80% 改善率判定尚未完成，保持未勾选。
- T027 已完成自动化和本地未登录浏览器失败/窄屏检查；登录后的回填→撤销→发送及完整探索模式仍未验收，保持未勾选。
- T028 已同步当前代码可证明的 Overview 和 README 行为；最终完整验收及收尾仍依赖 T026、T027，保持未勾选。原 T018 未被本轮润色验证替代。
