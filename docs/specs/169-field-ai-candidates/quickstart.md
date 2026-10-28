# 验证步骤

用 `python3 -m scripts.local_deploy.environment "/Users/mayuan/Codes/SC-Wiki"` 定位 Python。运行字段候选 pytest 与既有字段决定、提交门测试。真实本机 MySQL 测试显式启用 SCWIKI_CURRENT_MYSQL=1，使用外层回滚，不改用户草稿。

运行 frontend 定向 Vitest 和 `npm run build`。浏览器使用隔离接口：人工已通过→主动核对→字段设置候选→应用→刷新→提交。确认仅主动核对调用模型；截图包含当前值、候选、理由和按钮，顶部无候选正文。
