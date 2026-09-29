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
