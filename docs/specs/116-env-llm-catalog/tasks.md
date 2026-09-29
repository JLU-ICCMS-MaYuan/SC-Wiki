# 实施任务

**输入**：[Spec](spec.md)、[Plan](plan.md)、[Research](research.md)、[数据模型](data-model.md)、[契约](contracts/llm-catalog.md)。

- [x] T001 [US1] 在 `backend/tests/test_llm_catalog.py` 定义解析、排序、空组和错误配置测试。
- [x] T002 [US1] 实现 `backend/rag/llm_catalog.py` 与默认配置兼容。
- [x] T003 [US2] 在 `backend/tests/test_llm_catalog_api.py` 定义真实认证、目录脱敏和请求选择测试。
- [x] T004 [US2] 接入 `backend/rag/llm_context.py` 与 `backend/api/rag.py`，保护显式及默认服务端调用。
- [x] T005 [US2] 更新 `backend/ingest/upload_tasks.py`、`upload_jobs.py` 和凭据测试，保留模型快照且失效不回退。
- [x] T006 [US2/US3] 更新前端选择器、存储和对应 Vitest，保留个人配置。
- [x] T007 [US1/US3] 更新 Docker 编号环境传递与示例，验证 API/Worker 配置一致。
- [x] T008 [US3] 运行定向回归、生产构建和隔离 HTTP/Worker 验证；更新 Overview、配置指南及验收记录，按仓库规则提交。

依赖：T001→T002→T003→T004→T005/T006→T007→T008；全部任务串行实施。覆盖关系见 [Plan](plan.md) 的映射表。


## 阶段 2：部署与真实供应商收尾

- [x] T009 [US2] 在 backend/tests/test_issue73_error_safety.py、test_llm_request_paths.py 覆盖推理模型连接测试额度、截断/空响应和上游 model_not_found 的真实 SDK 边界。
- [x] T010 [US2] 修复 backend/api/rag.py 的单次连接测试：256 token 上限、30 秒读取超时；截断无正文、响应格式错误和模型不存在分别返回安全提示，不重试或切换模型。
- [ ] T011 [US3] 在当前 Mac 原生实例重新加载用户保存的 .env，通过实际代理/认证链验证编号目录及真实供应商；仅发送最小测试文本，不写业务论文或输出密钥。
- [ ] T012 [US3] 更新 README.md、docs/local-dev.md、Overview 与本 Spec 验证记录，补齐 Epic #21 关系并按实际结果收尾 Issue #116。

T011 已完成当前部署、目录脱敏、真实身份拒绝、LLM1/LLM3 调用；LLM2 保持用户指定地址，返回 HTML，协议待确认，因此不勾选完成。T012 的 README、指南、Overview 及 Epic 原生父子关系核对已完成，Issue 关闭等待 T011。
