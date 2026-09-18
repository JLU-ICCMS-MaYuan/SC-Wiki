# 验证步骤

## 本地隔离回归

Python 测试使用 `DEBUG=false`、`DATABASE_URL=sqlite:///:memory:`、`RAG_DATABASE_URL=sqlite:///:memory:` 和专用 `JWT_SECRET_KEY`（测试值，不使用业务密钥）。运行：

```bash
python -m pytest -q tests/01_decentralized_uploading/test_review_classification_save.py tests/01_decentralized_uploading/test_review_classification_current.py tests/01_decentralized_uploading/test_issue51_classification_workflow.py backend/tests/test_classification_catalog.py backend/tests/test_scientific_drafts.py tests/01_decentralized_uploading/test_scientific_evidence.py
frontend/node_modules/.bin/vitest run --config vitest.config.ts --no-file-parallelism tests/01_decentralized_uploading/review-classification-source.test.tsx tests/01_decentralized_uploading/admin-paper-classification-review.test.tsx tests/02_identity_governance/admin-edit-review.test.tsx tests/02_identity_governance/admin-edit-page.test.tsx tests/02_identity_governance/admin-scientific-data-edit.test.tsx tests/01_decentralized_uploading/evidence-proposals.test.tsx
```

在 `frontend/` 执行 `npm run build`，在 `goserver/` 执行 `go test ./handlers -count=1`。串行 UI 文件运行避免共享机器同时构建时超过既有单项超时。

## Go → Python → MySQL 实际审核

1. 使用独立临时 MySQL 实例，测试库名含 `test`，复制当前 scwiki 表结构，不复制业务行。设置 Python `DATABASE_URL`、`RAG_DATABASE_URL` 及 Go `SCWIKI_TEST_MYSQL_DSN` 指向该实例；使用同一个专用测试 `JWT_SECRET_KEY`。
2. 在测试库创建 `admin`、`superadmin`、`user` 三个夹具账号，包含 `real_name`、active 状态、邮箱已验证和 `session_version=0`，不使用真实用户数据。
3. 从仓库根启动 `python -m uvicorn review_classification_bridge:app --app-dir tests/01_decentralized_uploading --host 127.0.0.1 --port 13312`。
4. 在 `goserver/` 设置 `SCWIKI_CLASSIFICATION_TEST_URL=http://127.0.0.1:13312`，运行 `go test ./handlers -run '^TestSavedReviewClassificationsMySQL$' -count=1 -v`。
5. 两个角色均应通过真实科学保存、新家族关联、重复同值保存、Go 正式详情、实际 TypeScript 批准载荷、真实 Python `prepare-review` 和三状态审核历史。旧分类与未核对内容仍拒绝。

测试只截断批准后的发布/快照清理，人工确认由隔离夹具提供，不调用外部模型。测试服务仅绑定本机；结束后停止本轮测试进程，不连接正式索引。不能把旧 `TestCurrentMySQLQuickReview` 的通用成功替身当作本轮跨层验收。
