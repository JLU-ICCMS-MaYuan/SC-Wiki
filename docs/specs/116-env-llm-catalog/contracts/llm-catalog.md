# 编号模型配置契约

```dotenv
LLM1_NAME=模型一
LLM1_BASE_URL=https://gateway.example.com/v1
LLM1_MODEL=model-one
LLM1_API_KEY=
LLM3_NAME=模型三
LLM3_BASE_URL=https://gateway.example.com/v1
LLM3_MODEL=model-three
LLM3_API_KEY=
LLM_DEFAULT=LLM1
```

上例需填真实密钥才能成为完整配置；未使用模板请整组注释或留空，不填写 `LLM_COUNT`。

- `GET /api/rag/llm/catalog`：有效登录必需；返回 `data.items`，元素仅 `id/name/model`。没有目录时返回空数组。
- `X-LLM-Config-ID: LLM3`：选择服务端项；禁止同时传个人 `X-LLM-*` 四字段。未知 ID 返回 400；未登录/失效登录返回 401；配置格式错误返回不含值的 503。
- 未携带 ID 时：完整个人配置仍优先，否则使用原管理员默认、目录默认或旧环境默认。启用目录后的服务端 LLM 调用同样要求有效登录。
- `GET /api/rag/llm/current` 与健康状态保持安全元数据；只读论文/统计列表不调用 LLM。
- `.env` 修改后重建容器环境或重启宿主进程；Docker 中 API 和上传 Worker 使用同一配置文件。该动作不重建向量索引。
- 已删除目录项不会被浏览器静默替换；清除选择或显式选另一项才能继续。
