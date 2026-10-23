# 实施任务

输入：[spec.md](spec.md)、[plan.md](plan.md)、[research.md](research.md)、[data-model.md](data-model.md)、[契约](contracts/feed.md)。

- [x] T001 归档原图与需求；在 backend/news/models.py 和 alembic/versions/ 增加两张分类附属表。
- [x] T002 [US1/US2] 在 backend/news/classification.py 实现只读目录、分类校验、有限尝试与过期写回保护；新增专项 Python 测试。
- [x] T003 [US2] 在 backend/news/scheduler.py 接入小批次调度；验证采集独立、恢复和历史补齐。
- [x] T004 [US1] 扩展 goserver/handlers/news_feed.go 与 frontend/src/components/NewsFeed.tsx，复用中英文词典；验证分页和标签折叠。
- [x] T005 完成 Python/MySQL/Go/前端/浏览器及真实模型验证，更新 quickstart.md、资讯 Overview 与 README，纳入本任务独立提交。

验收依据：[quickstart.md](quickstart.md) 与 assets/ 中的真实模型结果、浏览器断言及截图。
Go 全套既有失败已记录；首轮 T001–T005 不包含业务部署，新增授权后的交付见 T007。

- [x] T006 [US3] 实现自然周/历史接口、周锚点、三栏入口及 Go/前端专项测试（FR-008）。
- [x] T007 执行已授权的业务库备份、迁移、历史补标、已提交制品发布及 Git 推送，记录真实结果（FR-009）；见 deployment-20261023.md 与公网/数据库验证附件。

依赖 T001→T002→T003/T004→T005。覆盖关系见 plan.md；先交付分类能力，再连通显示，最终记录运行边界。
