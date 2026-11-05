# 嵌入服务 HTTP 契约

- 外部 Base URL：`https://www.sc-wiki.com/embedding/v1`，正常验证 TLS；服务器内部为 GPU 127.0.0.1:8000。
- `GET /v1/models`、`POST /v1/embeddings` 在 Base URL 下按标准路径调用，均需有效 Bearer 密钥。GPU 的 /health 仅用于内部探测，不作为公网开放入口。
- model 为 Qwen/Qwen3-Embedding-4B，input 为字符串或字符串数组，encoding_format=float；dimensions 可省略或指定 32–2560，当前本地应用使用 1536。
- data 数量、索引与输入对应；向量有限、维度正确并归一化。不通过填充制造维度兼容。
- 无/错密钥为 401；非法模型、空批次、非法维度与超过 16384 Token 的输入为 4xx，不静默裁剪原文。
- Caddy 只允许 /embedding/v1/embeddings 与 /embedding/v1/models，其他 /embedding 路由 404；请求体上限 2MiB，原网站 /api 路径和体积规则保留。
- query 指令由本地 embed_texts(..., purpose="query") 按 EMBEDDING_QUERY_INSTRUCTION 添加，document 原文不变，其他供应商默认空指令保持旧行为。
- 当前物理主集合由 QDRANT_COLLECTION_NAME 指定，旧逻辑 paper_chunks 查询解析到新主集合。源集合保留，不能用旧模型查询新模型向量或反向混用。
- 请求与响应不记录密钥或业务正文，不声明与商业 text-embedding-v4 向量兼容。
