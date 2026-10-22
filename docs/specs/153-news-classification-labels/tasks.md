# 实施任务

输入：[spec.md](spec.md)、[plan.md](plan.md)、[research.md](research.md)、[data-model.md](data-model.md)、[契约](contracts/feed.md)。

- [x] T001 归档原图与需求；在 backend/news/models.py 和 alembic/versions/ 增加两张分类附属表。
- [x] T002 [US1/US2] 在 backend/news/classification.py 实现只读目录、分类校验、有限尝试与过期写回保护；新增专项 Python 测试。
- [x] T003 [US2] 在 backend/news/scheduler.py 接入小批次调度；验证采集独立、恢复和历史补齐。
- [x] T004 [US1] 扩展 goserver/handlers/news_feed.go 与 frontend/src/components/NewsFeed.tsx，复用中英文词典；验证分页和标签折叠。
- [x] T005 完成 Python/MySQL/Go/前端/浏览器及真实模型验证，更新 quickstart.md、资讯 Overview 与 README，纳入本任务独立提交。

验收依据：[quickstart.md](quickstart.md) 与 assets/ 中的真实模型结果、浏览器断言及截图。
Go 全套既有失败已记录；业务迁移、部署及远程链接不在已完成项内。

依赖 T001→T002→T003/T004→T005。覆盖关系见 plan.md；先交付分类能力，再连通显示，最终记录运行边界。
