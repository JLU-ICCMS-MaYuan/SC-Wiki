# 验证指南

## 前置条件

使用隔离空 MySQL 测试库，数据库名必须含 test，禁止连接业务数据库。先应用完整迁移；结构验证依赖 ASE。测试模型用固定来源响应，不消耗真实模型额度。

数据库连接由 `DATABASE_URL`、`RAG_DATABASE_URL` 和 `FRESH_MYSQL_DATABASE_URL` 同时指向隔离库，设置 `DEBUG=false` 和仅用于测试的 `JWT_SECRET_KEY`。从空库初始化时先 `alembic upgrade issue90_copy_v1`，依次执行 `python -m backend.scripts.migrate_issue90_properties` 的 `copy`、`final-sync`、`reconcile`、`read-switch`、`write-switch`、`observe`，最后在该隔离环境设置 `ISSUE90_CONTRACT_CONFIRMED=1` 并 `alembic upgrade 20260918_0108`。不要跳过实际表切换或只改 checkpoint。

## 自动验证

- Python：`python -m pytest backend/tests/test_paper_revisions.py`；集成部分使用隔离库环境变量 `FRESH_MYSQL_DATABASE_URL`。
- 前端：`npx vitest run --config vitest.config.ts tests/01_decentralized_uploading/paper-revision.test.tsx`。
- Go：在 goserver 运行 `go test ./handlers -run 'Test.*(Paper|Revision)'`。
- 构建：在 frontend 运行 `npm run build`。

## 用户路径

1. 准备原上传者、另一用户、独立管理员，及已拒绝论文；包含正文、两个结构和多条物性。
2. 删除隔离样本的原上传临时状态和审核快照，确认我的论文仍提供返修。
3. 修改标题和物性、保存、重开；正式论文值及 rejected 状态不变；将草稿时间设为两日前也能恢复。
4. 修改后重新来源核对，明确提交；论文 ID 不变、版本只加一、状态 pending。
5. 重试同一提交请求；确认没有第二次升版和重复历史。
6. 管理员重新审核；拒绝后再次返修。非上传者请求全部被拒绝。
7. 另一窗口或管理员修改基线，旧草稿保存/提交返回冲突；模拟持久化异常后整事务回滚。

实际执行结果记录到 validation.md；本地验收不等于已部署。

跨服务用例设置 `SCWIKI_TEST_GO` 为本机 Go 可执行文件，Python 会在临时样本上调用 `TestRevisionResubmittedReview`。不与会清空整个 `FRESH_MYSQL_DATABASE_URL` 的旧迁移测试共用数据库。
