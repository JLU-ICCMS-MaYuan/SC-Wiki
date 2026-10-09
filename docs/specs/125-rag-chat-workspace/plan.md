# 实施计划：RAG 对话工作区

**GitHub Issue**：[#125](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/125)

**日期**：2026-10-09

**Spec**：[spec.md](spec.md)

## 摘要

保留现有 RAG 引擎和 SSE 问答能力，新增账号主库中的云端会话与草稿润色接口；将页面三列卡片改为历史导航、中央对话和底部多行输入框。引用及数据库确认的关键词在正文中点击后，按需打开临时右侧详情。参见[技术决策](research.md)、[数据模型](data-model.md)和[接口契约](contracts/rag-chat.md)。

## 技术上下文

- **语言与框架**：后端 Python、FastAPI、SQLAlchemy、Alembic；前端 TypeScript 5.6、React 19、MUI 7。
- **主要依赖**：现有 RAG 服务、OpenAI 兼容模型客户端、JWT 账号体系、`react-markdown`。
- **数据存储**：会话与轮次在主应用数据库；文献详情和片段仍取当前 RAG 数据源；访客及旧历史保留在浏览器本机。
- **测试体系**：后端 `pytest`，前端 Vitest、React Testing Library 与 `npm run build`；跨浏览器账号隔离和页面交互使用人工或浏览器端到端验收。
- **目标平台**：现有桌面和移动浏览器，不新增原生应用。
- **性能目标**：不为常驻右栏预取文献详情；会话列表分页，关键词批量解析，保持流式首段可见；按[SC-001～SC-005](spec.md#成功标准)验收结果。
- **约束**：账号历史不得泄露给其他用户；模型凭据和内部推理不入库；已撤回或旧版论文片段不可通过历史链接读取。

## 质量门

| 约束来源 | 强制要求 | 设计如何满足 | 状态 |
| --- | --- | --- | --- |
| `AGENTS.md` | 只在 `mayuan` 修改，验证后按范围提交 | 实施前核分支和工作树，只暂存该 Feature 文件 | 规划通过 |
| 当前功能总览 | 现有本机多会话、SSE、灵感探索可用 | 保留访客流和现有事件；新云端模式增量扩展 | 规划通过 |
| [FR-005～FR-009](spec.md#功能需求) | 云端所有权、恢复、失败处理 | 主库账号外键、服务端历史、原子轮次及并发版本 | 规划通过 |
| [FR-011、FR-015](spec.md#功能需求) | 当前模型与发布状态 | 润色复用请求级模型配置；详情点击时重新校验 | 规划通过 |
| 文档规则 | 未实现内容不写当前 Overview | 最终实现验收后再由对应 Skill 回写 | 规划通过 |

## Feature 文档结构

```text
docs/specs/125-rag-chat-workspace/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/rag-chat.md
├── tasks.md
└── checklists/requirements.md
```

## 源代码结构

```text
alembic/versions/20261009_0125_rag_chat_conversations.py    # 拟新增，实施时接当前迁移头
backend/models.py
backend/api/rag.py
backend/services/rag_chat_conversations.py                   # 拟新增
backend/rag/service.py
backend/rag/search/sql_search.py
backend/tests/test_rag_chat_conversations.py                  # 拟新增
backend/tests/test_rag_chat_links.py                           # 拟新增
frontend/src/pages/RagPage.tsx
frontend/src/lib/useStreamingChat.ts
frontend/src/lib/ragConversations.ts                          # 拟新增
frontend/src/components/MarkdownMessage.tsx
frontend/src/components/RagSourceDrawer.tsx                   # 拟新增
frontend/src/pages/RagPage.test.tsx                            # 拟新增
frontend/src/i18n/zh/rag.ts
frontend/src/i18n/en/rag.ts
```

**结构选择**：后端会话服务负责所有权、持久化和幂等；RAG 服务继续负责生成与文献检索；页面只编排布局，hook 管理对话生命周期，独立 Drawer 负责详情。避免把账号存储逻辑写进检索服务，或在 `RagPage` 重复实现权限与来源规则。

## 需求到设计的映射

| 来源 | 设计组件或接口 | 验证方式 |
| --- | --- | --- |
| US1、FR-001～FR-004、FR-017 | `RagPage`、`useStreamingChat`、语言文案 | 空态、流式、探索模式、桌面及窄屏浏览器验收 |
| US2、FR-005～FR-009 | 主库模型、会话服务、会话 API、流式云端模式、本地导入 | 双账号隔离、跨浏览器恢复、失败与并发集成测试 |
| US3、FR-010～FR-012 | 润色 API、输入区候选预览 | 空输入、接受、取消、失败与编辑竞态测试 |
| US4、FR-013～FR-016 | 来源批量解析、现有论文详情、片段接口、Markdown 链接、Drawer | 已发布、无匹配、旧版本、关闭焦点测试 |
| SC-005 | 现有 SSE、灵感探索和模型配置回归 | 后端与前端回归、人工完整流程 |

## 阶段与依赖

1. **基础能力**：确认主库迁移头和现有 API 契约；先完成云端模型及所有权集成测试，再接流式完成轮次；保持访客接口兼容。
2. **布局与会话**：前端分离访客和登录会话状态，加入显式旧历史导入，改造页面结构并保持探索模式。
3. **润色**：独立后端接口和前端草稿候选交互；不触碰回答历史。
4. **来源详情**：批量解析有依据的目标，增加当前版本片段读取和临时 Drawer；删除常驻证据栏。
5. **验证与文档**：执行权限、持久化、模型失败、窄屏与回归验收；通过后回写当前功能总览并完成 Issue 的 Documentation Impact。

## 必要复杂度

| 复杂度 | 理由 | 控制方式 |
| --- | --- | --- |
| 主库新增会话与轮次 | 跨设备恢复和账号隔离必须有服务端事实来源 | 仅两类实体，不存逐 token 状态 |
| 请求幂等与序列检查 | SSE 断线重试及跨设备同时发送可能重复或乱序 | 每轮唯一请求 ID 与最后轮次版本 |
| 来源重新校验 | 论文审核状态和 revision 会变化 | 点击时验证，只按需加载详情 |
