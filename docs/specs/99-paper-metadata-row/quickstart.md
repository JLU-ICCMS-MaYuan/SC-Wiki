# 验证步骤

前置：加载本地 `.env`，使用 sc-wiki Python 环境和当前 MySQL；不输出连接凭据，不创建临时数据库。先执行 Alembic 升级到新增迁移，再让开发服务加载代码。

1. 在 `frontend/` 运行 `npm run test:upload-ui -- ../tests/01_decentralized_uploading/upload-task-editor-layout.test.tsx ../tests/01_decentralized_uploading/submit-validation-feedback.test.tsx`，然后 `npm run build`。
2. 在当前 MySQL 外层事务中使用真实提交函数创建待审核论文，读取期号 `S1` 和原页码范围，最终回滚；Go 真实更新和详情 handler 验证 `3-4` 与清空。
3. 打开当前服务的用户解析页面与管理员编辑页面，桌面及窄屏核对六项顺序、同一行、4:1:1:1:1:4；窄屏可滚动到 DOI。
4. 验证错误 DOI 仍能定位，旧论文期号为空可编辑。将实际执行命令、结果及限制写入 [验收记录](validation.md)。
