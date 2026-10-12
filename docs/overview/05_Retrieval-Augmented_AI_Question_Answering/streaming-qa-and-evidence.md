# 流式问答与证据

## 功能说明

基于检索结果构造上下文，通过 SSE 持续返回回答、引文、证据和状态事件，并在 React 中维护多轮会话。登录用户的完成轮次按账号保存在主应用数据库。

## 当前行为

- `/api/rag/chat/stream` 使用 `text/event-stream` 返回流式事件。
- 普通 `/chat` 与 `/chat/stream` 共用 Mentor 工具调用路径；仅显式 `explore=true` 进入灵感探索。`done` 事件携带最终答案，即使模型没有输出增量 token 也可获取完整结果。
- 物性工具的同步和异步调用共用 `search_property_records`；提供材料筛选并保留每条记录的条件、方法及论文版本。旧 `core/engine.py` 问答入口同样读取统一记录，不再按化学式只保留最高 Tc。
- 问答引擎先检索上下文，再调用 OpenAI 兼容的 LLM 接口生成回答。
- 事件包含回答增量、引文、证据、Top 结果及灵感模式相关数据。
- React hook `useStreamingChat` 消费 SSE。访客会话保存在浏览器本机，并显示“仅保存在本机”；登录用户可列出、读取、继续和删除本人云端会话，旧本地历史由用户显式导入。
- 登录会话的 `/chat/stream` 从服务端读取本人历史，在 `done` 前提交完整提问与回答；请求 ID 避免重复写入，轮次版本阻止另一设备的旧请求覆盖新消息。失败或中断的回答不作为完成轮次保存。
- 问答页左侧为历史、中央为对话及底部多行输入区，默认没有固定右侧证据栏。输入区的星形按钮调用独立润色接口，有效结果直接回填草稿，无需确认且不自动发送。每次实际替换提供一次撤销，可逐字恢复该次原文；继续编辑、再次润色、发送或切换上下文后撤销失效。
- 润色以固定 MIT 版本的 Prompt Optimizer 模板为基础，在超导语境下按需补充问题的分析维度、比较方式和证据要求，不回答原问题。保留当前模型选择，不读取会话历史或联网检索，不创建问答记录。生成结果必须完整、非空、不超过 1000 字符，并通过科学词元保留校验；语义正确性仍依赖模型与质量评测。
- 润色失败在输入区提示并保留草稿；等待期间可以继续编辑或主动发送。编辑、发送、新建/切换会话、账号变化与离开页面会使旧结果和旧错误失效，不能覆盖新输入。
- 回答中的引文、当前活跃物性定义、已批准论文关键词和关联材料名经数据库验证后可点击。点击时临时打开右侧文献或术语详情，并可继续查看当前批准 revision 的论文片段；撤回或过期片段返回不可访问。

- 发布到向量库的正式科学来源携带 source_kind、来源身份、论文 revision 与归因说明；问答和灵感引用保留这些字段。提供者结构明确显示实际提交者和“论文未明确支持”，不能写成论文报告的结论；派生值注明计算规则。React 会话保存并展示来源限定。
- 理论二级类型的正式来源转为检索片段时使用 `paper_synthesis`，说明它由 LLM 综合全文判断，所附引句是支撑片段，不把 `calculation/method/theory` 说成论文逐字记载。当前没有因本功能批量重新发布旧论文索引。（[#128](../../specs/128-fulltext-theoretical-subtype/spec.md)）

## 工作流程

用户提交问题；服务检查聊天配置；检索引擎生成上下文；问答引擎调用 LLM；API 将内部事件编码为 SSE；前端逐事件更新消息、证据卡片和会话状态。登录会话在完成时原子保存一问一答，刷新后从主库恢复；访客仍由本机保存。用户点击回答中的来源后，系统按当前发布状态重新读取详情或片段。

## 约束

- 需要检索数据可用且配置 LLM API key。
- 引文和证据来自当前检索结果，不等同于人工审稿结论。
- 访客本机历史不构成云端持久化；登录会话才具备服务端存储与跨设备读取接口。主库会话迁移须在目标环境应用后才能使用。
- 云端会话接口按当前有效账号过滤；模型密钥不写入会话。来源链接只表示数据库当前可访问的匹配结果，不等同于人工审稿结论。

## 代码与测试

- `backend/api/rag.py`
- `backend/rag/service.py`
- `backend/rag/prompts/prompt_polish.md`
- `backend/scripts/evaluate_prompt_polish.py`
- `backend/rag/core/engine.py`
- `backend/rag/agent/mentor.py`
- `backend/rag/agent/tools.py`
- `frontend/src/pages/RagPage.tsx`
- `frontend/src/lib/useStreamingChat.ts`
- `frontend/src/lib/ragConversations.ts`
- `frontend/src/components/MarkdownMessage.tsx`
- `frontend/src/components/RagSourceDrawer.tsx`
- `backend/services/rag_chat_conversations.py`
- `alembic/versions/20261009_0125_rag_chat_conversations.py`
- `backend/tests/test_rag_chat_conversations.py`
- `backend/tests/test_rag_chat_links.py`
- `tests/05_rag_question_answering/`

## 相关变更记录

- [Issue #107：修复 RAG 多入口读取与普通问答路径](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/107)。
- [Issue #125：RAG 对话入口、提示词润色与云端会话](../../specs/125-rag-chat-workspace/spec.md)。

## 已知问题

- 外部 LLM 的可用性、费用和响应稳定性不由本项目保证。
- 润色增强已通过后端路由/SDK 边界测试、前端回填/撤销/竞态测试及构建；真实模型结果与人工评审边界见 [#125 验证记录](../../specs/125-rag-chat-workspace/quickstart.md)。本地未登录浏览器已核对失败保留与窄屏布局，登录后的完整浏览器链路、真实部署迁移和账号跨设备验收仍需完成。

语义检索的正式科学来源支持 human_review：保存管理员身份、理由与版本，引用和上下文明确标注人工判断及论文未直接支持，不表述为论文报告或 AI 已验证；融合提示逐个保留来源片段及各自归因。

采用论文推断或通用知识推测后，正式来源同时保留 `adopted_basis` 与管理员人工理由。发布及检索上下文明确标注“根据论文推断”或“通用知识推测”，人工批准和 AI 认可不会把它改成论文直接报告。空可选字段与未采用的无当前值建议不发布为科学结论。参见 [#109](../../specs/109-field-evidence-and-ai-suggestions/spec.md)。
