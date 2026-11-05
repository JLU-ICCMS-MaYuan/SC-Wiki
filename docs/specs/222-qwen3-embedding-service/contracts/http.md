# 嵌入服务 HTTP 契约

- 地址：服务器 127.0.0.1:8000；外部通过已验证 SSH 通道访问，不假设平台自动提供公网端口。
- `GET /health`：存活/就绪探测，不视作推理成功。
- `GET /v1/models`：有效 Bearer 密钥后返回 `Qwen/Qwen3-Embedding-4B`。
- `POST /v1/embeddings`：有效 Bearer 密钥；model 固定为上述名字，input 为字符串或字符串数组，encoding_format 为 float，dimensions 可省略或指定 32–2560，至少验收 1536 与 2560。
- 响应遵循 OpenAI embedding list：每个 data 项包含 index 与 embedding，数量和索引对应原输入；向量有限、指定维度且 L2 归一化。
- 缺少/错误密钥返回 401；非法模型、维度、空输入及超长输入返回 4xx，记录实际状态码；不接受静默伪成功。
- 请求和响应不得记录密钥或业务正文；访问日志禁用。
- 语义检索的 query 由调用者使用 `Instruct: Given a research paper query, retrieve relevant scientific passages that answer the query\nQuery: <问题>`，文献直接编码。
- 本契约不承诺商业 v4 向量兼容，也不创建聊天接口。
