# 验证步骤

1. 在 `frontend/` 执行 `npm run test:upload-ui -- ../tests/01_decentralized_uploading/admin-paper-classification-review.test.tsx ../tests/02_identity_governance/admin-edit-review.test.tsx`，再执行 `npm run build`。
2. 显式加载当前 `.env`，设置 `SCWIKI_CURRENT_MYSQL=1` 和由当前连接生成的 `SCWIKI_TEST_MYSQL_DSN`，在 `goserver/` 执行 `go test ./handlers -run '^TestCurrentMySQLQuickReview$' -count=1 -v`。不输出连接凭据，不建立临时数据库。
3. 在当前开发服务分别进入 `/admin` 与 `/superadmin`，打开小锤子并展开审核结果，确认三状态和提示。现有论文只读检查，不实际批准。
4. 使用回滚事务内构造的论文验证三个真实状态及审批历史；Evidence 不完整场景仍应返回原错误。
