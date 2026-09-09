# #73 局部修复验证记录

## 2026-09-09：三个错误边界

本轮只修复连接探测误报成功、上游错误经日志/响应回显、用户配置的 Reranker 吞掉 401/403。
不代表 #73 全体验收完成。Claude 按用户要求停止测试，保留未验收结论。

### 证据

- 新增 `backend/tests/test_issue73_error_safety.py`。首轮 11 项中 10 项失败，复现 HTML/异常结构/
  空正文误报成功、日志与响应包含合成凭据以及认证失败未抛错；修复并扩展后 13 项全部通过。
- 使用真实 OpenAI SDK 与 `httpx.MockTransport` 解析模拟上游响应，通过 FastAPI 测试客户端
  检查探测 HTTP 结果；每次只发一个模拟请求且保留 `max_tokens=1`。
- 覆盖 401/403 的明确异常、打印的异常链、非认证降级日志、API 内部错误响应、JSON 重试日志和
  普通生成流的错误输出。仅使用假密钥，没有读取 `.env.issue73.local` 或调用真实 LLM。
- 联合专项：下列 7 个文件共 **39 项通过**；532 条为测试输出中的依赖弃用警告。

```bash
source "scripts/lib-local.sh"
JWT_SECRET_KEY=issue73-test-only DATABASE_URL=sqlite:// "$PY_BIN/python" -m pytest \
  "backend/tests/test_issue73_error_safety.py" \
  "backend/tests/test_llm_request_paths.py" \
  "backend/tests/test_llm.py" \
  "backend/tests/test_llm_context.py" \
  "backend/tests/test_llm_client_coverage.py" \
  "backend/tests/test_default_llm_config_api.py" \
  "tests/01_decentralized_uploading/test_upload_llm_credentials.py" -q
```

### 边界

- 思考模型可能在 1 Token 额度内没有正文；此时探测未通过，不据此认定密钥错误，也不自动增加
  Token 或重试。HTTP 200 和传输可达不等于模型输出验收成功。
- 本轮覆盖指定的错误输出路径，不把局部假密钥测试当作数据库、生产日志和 Nginx 零泄露审计。
- 未重新执行此前未通过的完整后端/上传/前端回归，不将其失败归为已修复；不改其他 Issue 的文件。
- 生产日志审计、部署环境人工验收、真实 Redis/Worker 完整生命周期与其它既有关闭门槛仍待完成。
