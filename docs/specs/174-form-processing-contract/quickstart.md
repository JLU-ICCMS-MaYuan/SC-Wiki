# 验收与回归入口

在 frontend 运行 `npm run test:form-contract`，执行完整宿主、缓存/标记、保存及输入边界检查；`npm run test:form-contract:mutation` 验证已知回退能被检出；`npm run build` 检查类型和生产构建。CI 使用同样入口，不需要业务数据库或模型密钥。

手工检查：上传、返修和两种管理员分别打开五张材料卡片，修改标题、首张卡片晶系、非法元素数、中文输入、中间数字和侧栏值。观察无关卡片保持，真实提示更新；无变化不写入，修改后保存重开一致；删除前卡不串字段，失败或冲突不丢输入。

大草稿验收使用浏览器脚本和隔离 API；同一夹具、同一浏览器环境测量修复前后。具体计数、运行命令与覆盖边界在验收完成后记录于 validation.md。此文档不声明全站其他入口已验收。

脚本 `tests/01_decentralized_uploading/form-contract-browser.mjs` 通过 `FORM_CONTRACT_DRAFT` 和 `FORM_CONTRACT_SUMMARY` 读取仅供本地测试的固定草稿／摘要 JSON；通过 `PLAYWRIGHT_MODULE`、`CHROMIUM_PATH` 指定本机浏览器依赖，`FRONTEND_URL` 指向待测源码的 Vite 实例，`FORM_CONTRACT_OUTPUT` 指定统计输出。脚本拦截所有 API，副本输入不会保存到真实服务；原草稿和证据正文不提交仓库。

比较基线时，可在临时目录导出指定 Git 提交的 frontend 并在独立端口启动 Vite；不切换共享工作树。测量必须串行，避免两个浏览器同时争用 CPU。注入回退只在测试编译器内发生，不改变文件或用户数据。
