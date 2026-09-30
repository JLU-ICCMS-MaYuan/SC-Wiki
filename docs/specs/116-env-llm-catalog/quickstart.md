# 配置与验收

1. 在私有 `.env` 填写一组或多组 `LLM<n>_NAME/BASE_URL/MODEL/API_KEY`。编号允许缺号；可选 `LLM_DEFAULT=LLM1`。
2. 重新加载 API/Worker；Docker 需重新创建应用容器环境，单纯 restart 不加载新环境变量。实际加载方式以部署说明为准。
3. 登录后打开侧栏模型配置，选择服务端模型，无需输入服务端密钥；保存后发起问答或论文解析。
4. 原个人供应商仍可填写个人密钥。Embedding 与 SMTP 继续单独配置。
5. 删除当前选择对应编号并重启后，应明确提示失效，不换用其他模型。匿名请求或过期令牌应在上游调用前被拒绝。
6. 核验目录响应、浏览器存储、任务状态和错误中都没有服务端密钥。

所有示例使用假密钥。真实供应商验收需要部署者自行准备可用配置，不将密钥写进 Spec 或 Git。

## 验证记录

2026-09-29 验证：

- 后端 61 项通过：目录、真实 JWT/账号状态/会话版本、双 HTTP 上游选择、SSE、旧默认配置、错误脱敏及上传凭据回归。命令范围为 `backend/tests/test_llm_catalog*.py`、`test_llm_env_export.py`、`test_llm_context.py`、`test_llm_request_paths.py`、`test_llm_client_coverage.py`、`test_default_llm_config_api.py`、`test_issue73_error_safety.py` 及上传凭据测试。
- RQ 验证使用独立 Redis 和真实 fork Worker：两份编号快照发送到指定 HTTP 上游、TTL 存在、完成后凭据删除，未调用默认配置；另外覆盖了终态重复执行保持原结果和取消请求优先。不只用 FakeRedis 推定通过。
- 前端 6 项通过：原个人入口、目录选择、失效 ID、浏览器无服务端密钥、退出登录不再发送编号。命令：`NODE_OPTIONS=--no-experimental-webstorage frontend/node_modules/.bin/vitest run --config vitest.config.ts tests/01_decentralized_uploading/llm-provider-switcher.test.tsx tests/01_decentralized_uploading/llm-catalog-switcher.test.tsx`。宿主 Node 26 的实验 localStorage 会干扰旧 Vitest，按命令关闭该特性，未修改项目依赖版本。
- `npm --prefix frontend run build` 通过，保留既有大分包提示。
- 真实 Compose 容器确认导出密钥中的美元符、引号和反斜杠原样传递，且数据库/SMTP 密码未导出。
- 独立 Nginx → Go → 当前 Python 源码 → 两个 HTTP 模型端点验证通过：目录无密钥，匿名/伪造登录被拒绝，两个编号正确使用各自密钥和型号。代理使用既有未改动镜像，Python 使用当前验证源码挂载。
- 修正 #73 旧测试会话替身缺少 `scalar` 及未替换模块内会话工厂的问题，使错误脱敏测试能够到达待测生成异常；没有更改该业务逻辑。
- `git diff --check` 通过。实际密钥不进入提交；测试使用假凭据，未调用真实付费供应商。

## 当前 Mac 实例与真实验收（2026-09-29 收尾）

当前实例已经由 #117 切换为 Mac 原生服务，源码来源为当前工作区；旧 Lima 目录已删除，
不再作为 #116 部署前置条件。API 与三个 Worker/Scheduler 进程已重新加载私有 .env。
用户授权本次文档收尾，根 README 已补充编号模型配置、重载命令和协议边界。

真实网站入口 http://127.0.0.1:5173 的 Vite→Go→Python 链验证：

- 匿名和伪造登录的连接测试返回 401；有效账号的短期测试凭据只驻留进程内存，不写入文件。
- 已登录目录返回 3 个配置项，只包含 id/name/model，响应不包含真实密钥或地址。
- 当时的 LLM1 deepseek-v4-pro 和 LLM3 gpt-6-sol 均通过网站连接测试，响应模型与选择一致。
- LLM2 的 claude-opus-5-5 保持用户指定的不带 /v1 的 Base URL。实际
  POST /chat/completions 返回 HTTP 200、text/html，内容是网页，不是模型响应；
  网站明确返回 502 / LLM_RESPONSE_INVALID，未自动修改路径或切换模型。
- 真实调用仅发送“Reply with just OK.”等最小测试文本，不上传论文或业务数据。
  本项不代表全部 RAG/论文语义链已对每个供应商验收，也不验证 Embedding 或 SMTP。

## 连接测试修复与回归

原测试 max_tokens=1 会让推理模型耗尽额度但没有正文，误报服务不可达。
现在单次请求上限为 256 token，读取超时 30 秒，无自动重试或模型回退。
无正文且 finish_reason=length 返回 LLM_OUTPUT_LIMIT；网页或空响应返回
LLM_RESPONSE_INVALID；网关以 HTTP503 携带 model_not_found 时按模型不存在处理。
仍要求非空正文才能报告连接成功，不暴露思考内容、上游原始异常或凭据。

本次定向回归：后端 66 项、前端 6 项全部通过；后端包含独立原生 Redis 与真实 RQ Worker、
实际 SDK 响应解析及登录/路由/凭据清理测试。测试使用临时目录、SQLite 和假密钥，
不写入当前实例的业务数据。修正旧清理测试使用 /data 的宿主路径依赖，
测试自身明确使用 tmp_path。前端未修改，实现阶段生产构建通过的记录仍见上文。

## LLM2 地址修正后的最终验收（2026-09-29）

网关直接探测表明，同一主机的根路径 /chat/completions 返回网页，而 /v1/chat/completions
返回标准 OpenAI 兼容 JSON，因此原问题是 Base URL 缺少 /v1，不需要新增协议。用户随后将
LLM2 改为带 /v1 的地址与 gpt-6-sol，并删除原 LLM3。重启 API 与三个 Worker/Scheduler 后，
经 http://127.0.0.1:5173 的 Vite→Go→Python 链复验：

- 匿名、伪造登录的目录请求及匿名连接测试均返回 401。
- 已登录目录返回 2 项（LLM1 deepseek-v4-pro、LLM2 gpt-6-sol），仅含 id/name/model，不含密钥或地址。
- LLM1、LLM2 连接测试均返回 200，响应型号与所选编号一致。
- 已删除的 LLM3 返回 400，未回退到其他模型。

上方旧 LLM2 记录保留为问题轨迹。本机脱敏证据位于 .local/issue116-live-verification.json。
#116 全部验收项完成。
