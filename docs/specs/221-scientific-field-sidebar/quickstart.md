# 验收入口

历史迁移证据：migration-manifest.json、migrated-records.md、legacy/ 及 verification/verify_migration.py。原始摘要不改写；默认校验历史归档及引用。`--check-current` 只对应建档迁移那次文档快照，后续正常实施编辑不冒充该旧快照。

产品验收与限制见 [validation.md](validation.md#产品实现验收2026-11-05)，结构化结果见 assets/implementation.json。科学字段颜色仅引用 #220。

在仓库根执行：

```sh
npm run test:field-contract --prefix frontend
npm run test:form-contract --prefix frontend
npm run test:form-contract:mutation --prefix frontend
npm run build --prefix frontend
```

真实 Chrome 验证脚本为 tests/01_decentralized_uploading/sidebar-field-review-browser.mjs，使用 FRONTEND_URL、PLAYWRIGHT_MODULE、CHROMIUM_PATH、FIELD_REVIEW_BROWSER_OUTPUT；指向独立本地 Vite，所有业务 API 均由独立会话拦截，不写用户草稿。四宿主各执行通过、未通过、技术失败和取消。

固定15卡200字段前后性能脚本为 tests/01_decentralized_uploading/sidebar-performance-browser.mjs；分别指向5198旧版和5199新版的隔离 Vite。PressureEditor 仅在浏览器拦截响应中加入计数，不改变工作树。源码副本路径须使用真实路径，两个 Vite 使用各自缓存，避免重复 React 或未经转换的 TSX 造成假失败。

后端 test_sidebar_feedback.py 覆盖公开摘要流、真实文档工具、隔离 Redis 小投影及实际 worker 的结果存储往返、取消保护；科学语义还需参考真实 PDF 定向重核证据，不用夹具代替真实来源。


补充PDF回归：运行 tests/01_decentralized_uploading/test_sidebar_pdf_evidence.py，覆盖长PDF、超限、PDF与文本共同输入、实际worker成功／未通过／技术失败／取消、读取反馈幂等及令牌。真实CaH6补证验收见 validation.md 的“补充PDF实际读取验收”。
