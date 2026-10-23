# 验证与运行

启动方式不变：`bash scripts/dev.sh start news-worker news-scheduler`。平台自动选择 Worker，不需要设置绕过 fork 安全检查的环境变量。

在项目 Python 环境执行 test_news_scheduler.py、test_news_collection.py、test_news_compose.py，本轮 26 项通过。

查询 `/api/news/feed?period=week&kind=preprint&page_size=1` 及另外两种 kind，结合 sources.last_success_at 判断是否实际恢复。线上与本机独立，不把线上计数作为本地结果。

遗留锁清理是本次确认无活跃作业后的单次恢复，不提供无条件删锁命令。正常运行由 TTL 和 finally 释放保护。
