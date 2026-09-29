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

- 后端 55 项通过：目录、真实 JWT/账号状态/会话版本、双 HTTP 上游选择、SSE、旧默认配置、错误脱敏及上传凭据回归。命令范围为 `backend/tests/test_llm_catalog*.py`、`test_llm_env_export.py`、`test_llm_context.py`、`test_llm_request_paths.py`、`test_llm_client_coverage.py`、`test_default_llm_config_api.py`、`test_issue73_error_safety.py` 及上传凭据测试。
- RQ 验证使用独立 Redis 和真实 fork Worker：两份编号快照发送到指定 HTTP 上游、TTL 存在、完成后凭据删除，未调用默认配置。不是仅用 FakeRedis 推定通过。
- 前端 6 项通过：原个人入口、目录选择、失效 ID、浏览器无服务端密钥、退出登录不再发送编号。命令：`NODE_OPTIONS=--no-experimental-webstorage frontend/node_modules/.bin/vitest run --config vitest.config.ts tests/01_decentralized_uploading/llm-provider-switcher.test.tsx tests/01_decentralized_uploading/llm-catalog-switcher.test.tsx`。宿主 Node 26 的实验 localStorage 会干扰旧 Vitest，按命令关闭该特性，未修改项目依赖版本。
- `npm --prefix frontend run build` 通过，保留既有大分包提示。
- 真实 Compose 容器确认导出密钥中的美元符、引号和反斜杠原样传递，且数据库/SMTP 密码未导出。
- 独立 Nginx → Go → 当前 Python 源码 → 两个 HTTP 模型端点验证通过：目录无密钥，匿名/伪造登录被拒绝，两个编号正确使用各自密钥和型号。代理使用既有未改动镜像，Python 使用当前验证源码挂载。
- 修正 #73 旧测试会话替身缺少 `scalar` 及未替换模块内会话工厂的问题，使错误脱敏测试能够到达待测生成异常；没有更改该业务逻辑。
- `git diff --check` 通过。实际密钥不进入提交；测试使用假凭据，未调用真实付费供应商。

## 尚未完成的环境事项

此前 Mac 的 `~/.scwiki-runtime` 在本轮检查时不存在，故没有重建该目录或覆盖现有容器数据。本轮属于源码实现和独立部署链验证，不代表原网站已更新；恢复实际部署需要先确认运行目录。根 README 的明确编辑限制及建议见 [README 修改建议](readme-suggestion.md)。Issue 保持打开追踪部署与文档关闭门，不将这些事项写成已完成。
