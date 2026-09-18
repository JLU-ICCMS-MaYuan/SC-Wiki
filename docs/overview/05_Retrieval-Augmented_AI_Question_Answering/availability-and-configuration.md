# 可用性与配置

## 功能说明

集中解析 RAG 数据路径、异步数据库、Qdrant、Embedding 和 LLM 设置，并分别报告检索与聊天能力是否可用。

## 当前行为

- `RagSettings` 管理数据根目录、数据库、向量库和 LLM 参数。
- 默认数据根指向仓库外的相邻数据集目录。
- 健康检查分别判断数据库、向量库和聊天配置，检索可用与聊天可用不是同一状态。
- 服务层在缺少数据或 LLM 时返回明确的不可用错误或降级信息。
- 侧栏底部的“切换模型”可配置服务端默认、DeepSeek、Kimi、GLM、Qwen、OpenAI、Claude 或自定义的 OpenAI 兼容端点。展开时显示当前供应商与模型摘要，收起时通过图标提示查看完整名称，点击打开同一配置弹窗；该入口位于语言切换上方。
  用户配置通过 `X-LLM-Provider`、`X-LLM-Base-URL`、`X-LLM-Model`、`X-LLM-Api-Key` 传递，
  个人配置保存在浏览器 `localStorage`，调用时随请求头传给服务端。上传后台任务另以带 TTL 的 Redis 凭据键短暂传递配置，终态删除，详见[上传解析管线](../01_Decentralized_Uploading_of_Superconductivity_Data/pdf-parsing-pipeline.md)；服务端不把用户 API key 写入数据库或公开任务状态。
- 个人 API Key 输入默认掩码；用户可在当前表单内显式显示或隐藏它，关闭面板后仍只以掩码摘要展示。

## 工作流程

应用首次调用时加载设置；服务健康检查验证文件和目录；搜索端点要求数据库与向量能力；对话端点额外检查当前请求的 LLM 凭据。
用户配置失败时不会静默回退到服务端密钥。`POST /api/rag/llm/test-connection` 用最小请求验证模型和凭据，
并映射认证失败、模型不存在、不可达和超时错误。
连接测试只有在返回的 `choices[].message.content` 包含非空正文时才报告成功；HTML 网页、缺少
记录或空正文均返回 `LLM_UNREACHABLE`。探测保持单次请求、`max_tokens=1`，因此思考模型若没有
在此额度内输出正文，只能判为本次未验证成功，不自动增加额度或重试。
Reranker 使用用户配置收到 401/403 时返回 `LLM_USER_CREDENTIAL_FAILED`，不吞掉认证失败，
不改用服务端凭据；其他评分失败仍保留原始排序。重排和 JSON 重试日志、普通流式生成错误文本及
RAG 通用内部错误响应不拼接上游异常原文，避免上游回显的密钥进入这些输出。
`GET /api/rag/llm/current` 仅返回供应商显示名、模型名和来源（`server` / `browser`），供侧栏明确显示
当前模型；响应不包含 Base URL、API key、请求头或密钥掩码。
部署可用 `LLM_PROVIDER_NAME` 显式标注网关上游，例如当前默认配置为 `OpenAI · gpt-5.6-sol`；不再仅按
Base URL 推断。超级管理员可在工作台更新默认供应商、Base URL、模型和密钥，配置原子写入 API 与
Worker 共用的 `/data/runtime/default_llm.json`，后续调用立即生效。仅超级管理员可读取或修改该配置，
密钥字段从不回显，空密钥表示保留既有值。工作台默认以摘要卡片展示当前模型；只有点击“编辑”才打开
可修改表单，当前角色卡片使用普通文本布局并对溢出截断。

## 约束

- 缺少 `RAG_DATA_ROOT` 对应数据、Qdrant 或 API key 时，部分或全部能力不可用。
- 主应用数据库正常不表示 RAG 数据库正常。
- 配置值可能来自环境变量，文档不记录任何实际密钥。

## 代码与测试

- `backend/rag/config.py`
- `backend/rag/service.py`
- `backend/api/rag.py`
- `tests/05_rag_question_answering/`

## 相关变更记录

实现来源：[Issue #73：顶栏 AI 供应商切换](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/73)。

入口布局更新：[Feature #101：全角色统一可收起侧栏](../../specs/101-unified-collapsible-sidebar/spec.md)。

## 已知问题

- 外部数据目录的部署和同步流程待核验。
- [Issue #73](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/73) 的六家供应商真实兼容性、部署环境四条 AI 调用链路与上传 Worker 生命周期、生产数据库及应用/Nginx 日志密钥泄露审计和完整回归仍待验收。现有[专项验证记录](../../specs/73-user-llm-provider-switch/validation.md)使用假密钥与模拟上游响应，不能证明上述环境验收已通过。
- #73 的旧验收脚本仍称“顶栏”；当前全局入口已由 #101 调整为侧栏底部的“切换模型”，实际页面核对应使用此入口。
