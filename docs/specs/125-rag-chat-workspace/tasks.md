# 实施任务：RAG 对话工作区

**输入**：[spec.md](spec.md)、[plan.md](plan.md)、[research.md](research.md)、[data-model.md](data-model.md)、[接口契约](contracts/rag-chat.md)

所有任务均未实施。任务编号用于技术拆解，进度以 [Issue #125](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/125) 为准。

## 阶段 1：基础能力

**目的**：让云端会话具备受保护的主库事实来源，再接入页面。

- [ ] T001 [US2] 在 `backend/tests/test_rag_chat_conversations.py` 先写主库事务、账号隔离、导入幂等、轮次原子提交和跨设备冲突测试，对应 FR-005～FR-009、SC-002。
- [ ] T002 [US2] 在 `backend/models.py` 与 `alembic/versions/20261009_0125_rag_chat_conversations.py` 增加主库会话和完成轮次及约束，对应 FR-005、FR-006、FR-009。
- [ ] T003 [US2] 在 `backend/services/rag_chat_conversations.py` 实现所有权校验、分页列表、删除、显式导入、请求幂等和序列检查，对应 FR-005～FR-009。
- [ ] T004 [US2] 在 `backend/api/rag.py` 扩展会话 API 与 `/chat/stream` 云端模式，完成后先提交轮次再发送 `done`，保留访客旧请求契约，对应 FR-005～FR-009。

## 阶段 2：US1 与 US2——对话布局和历史（P1）

**目标**：用户进入页面即可提问，并清楚区分本机历史与云端历史。

**独立验收**：`quickstart.md` 的布局、本机与云端、账号隔离、失败与并发场景通过。

- [ ] T005 [US1] 在 `frontend/src/pages/RagPage.test.tsx` 先写空态、历史切换、窄屏导航、云端同步标识与旧历史显式导入测试，对应 FR-001～FR-003、FR-005、FR-007、FR-008、SC-001、SC-002。
- [ ] T006 [US2] 在 `frontend/src/lib/ragConversations.ts` 封装云端会话、导入和失败状态请求，对应 FR-005～FR-009。
- [ ] T007 [US2] 在 `frontend/src/lib/useStreamingChat.ts` 区分访客本机与登录云端状态，处理流式完成、重试、切换账号和导入旧历史，对应 FR-005～FR-009。
- [ ] T008 [US1] 在 `frontend/src/pages/RagPage.tsx` 改为左侧历史、中央对话及底部多行输入布局，移除常驻证据栏并保留探索模式，对应 FR-001～FR-004、SC-001、SC-005。
- [ ] T009 [US1] 在 `frontend/src/i18n/zh/rag.ts` 与 `frontend/src/i18n/en/rag.ts` 增加历史、同步、错误和键盘辅助文案，对应 FR-017。

## 阶段 3：US3——星形润色（P1）

**目标**：用户能安全预览 AI 改写并自行选择是否采用。

**独立验收**：`quickstart.md` 的五类润色场景通过。

- [ ] T010 [US3] 在 `backend/tests/test_rag_chat_conversations.py` 先写空草稿、模型错误、输出边界、保留科学符号和不创建问答轮次的测试，对应 FR-010、FR-011、SC-003。
- [ ] T011 [US3] 在 `backend/api/rag.py` 与 `backend/rag/service.py` 增加独立润色接口，复用请求级模型配置，对应 FR-010、FR-011。
- [ ] T012 [US3] 在 `frontend/src/pages/RagPage.test.tsx` 先写预览、接受、取消、失败及编辑竞态测试，对应 FR-010～FR-012、SC-003。
- [ ] T013 [US3] 在 `frontend/src/pages/RagPage.tsx` 实现输入框星形按钮与候选预览，接受后仅替换当前草稿，对应 FR-002、FR-010～FR-012。

## 阶段 4：US4——回答内来源与临时详情（P1）

**目标**：点击真实来源后临时查阅文献，不占据默认布局。

**独立验收**：`quickstart.md` 的已批准、无匹配、旧版本和关闭恢复场景通过。

- [ ] T014 [US4] 在 `backend/tests/test_rag_chat_links.py` 先写已批准论文、物性定义、重名、无匹配、撤回和旧版片段验证，对应 FR-013～FR-015、SC-004。
- [ ] T015 [US4] 在 `backend/rag/search/sql_search.py` 与 `backend/api/rag.py` 增加有界来源解析和当前版本片段读取，复用已批准论文过滤，对应 FR-013～FR-015。
- [ ] T016 [US4] 在 `frontend/src/pages/RagPage.test.tsx` 先写引文/关键词点击、Drawer 关闭与焦点恢复测试，对应 FR-013～FR-016、SC-004。
- [ ] T017 [US4] 在 `frontend/src/components/MarkdownMessage.tsx`、`frontend/src/components/RagSourceDrawer.tsx` 和 `frontend/src/pages/RagPage.tsx` 实现可验证链接、右侧按需详情与关闭恢复，对应 FR-004、FR-013～FR-016。

## 阶段 5：收尾与回归

- [ ] T018 在 `backend/tests/test_rag_chat_conversations.py`、`backend/tests/test_rag_chat_links.py`、`frontend/src/pages/RagPage.test.tsx` 和 `docs/specs/125-rag-chat-workspace/quickstart.md` 运行并记录跨账号、跨浏览器、模型失败、来源版本与原有探索模式回归，对应 SC-001～SC-005。
- [ ] T019 实施验收后使用 `big-project-overview-maintainer` 更新 `docs/overview/05_Retrieval-Augmented_AI_Question_Answering/streaming-qa-and-evidence.md`；检查 `README.md` 是否需补问答使用说明，并完成 Issue #125 的 Documentation Impact。

## 依赖与执行顺序

- T001 → T002 → T003 → T004 是云端主路径；同一文件上的任务按编号串行。
- T005 可在后端基础能力建设时准备；T006 → T007 → T008 → T009 后验收 US1/US2。
- T010 → T011、T012 → T013 是润色后端与前端链路；T013 接受布局 T008 的输入区。
- T014 → T015、T016 → T017 是来源后端与前端链路；T017 接受布局 T008 的消息区。
- T018 依赖全部功能任务；T019 依赖真实实现和验收，不能提前将设计写成当前事实。

## 需求覆盖

| 来源 | 任务 | 验收依据 |
| --- | --- | --- |
| US1、FR-001～FR-004、SC-001 | T005、T008、T017、T018 | 默认无右栏，桌面/窄屏、流式与探索模式 |
| US2、FR-005～FR-009、SC-002 | T001～T007、T018 | 主库恢复、账号隔离、显式导入、失败并发 |
| US3、FR-010～FR-012、SC-003 | T010～T013、T018 | 空输入、接受、取消、失败、编辑竞态 |
| US4、FR-013～FR-016、SC-004 | T014～T018 | 来源验证、当前版本、临时详情、焦点 |
| FR-017、SC-005 | T008、T009、T018 | 中英文、键盘、普通问答、探索与模型回归 |

## MVP 与增量策略

1. 完成云端基础能力与 US1/US2，可独立交付清爽布局和跨设备历史。
2. 加入 US3 的独立草稿润色，不改变问答持久化契约。
3. 加入 US4 的来源链接与按需详情，再执行完整回归和文档回写。
