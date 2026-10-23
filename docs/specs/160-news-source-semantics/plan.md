# 实施计划

**Issue**：[#160](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/160)
**Spec**：[spec.md](spec.md)

## 技术上下文与方案

Python/HTTPX/feedparser/SQLAlchemy/RQ，Go/GORM 与 React。复用资讯队列与表，不增加服务和数据库迁移。
Sources 的发布商任务获取配置目录中的官方RSS，并与Crossref补充结果组合；单入口失败通过 partial_error 记录。
Transport 只访问固定端点，区分认证/拒绝/限流；仍保留超时、响应大小和速率上限。
Crossref 查询使用常见完整词形而非只用词根，期刊用ISSN过滤且逐条校验，日期优先 published-online。
查询按最近至少30天的发表日期过滤，并以 indexed 倒序游标分页；Crossref不支持 published 排序与cursor同时使用，公开列表仍按发表时间排序。HTTP400记bad_request，不将所有4xx归为反爬。
OpenAlex 无Key最多取得允许的第一页，发现后续页时 partial；有Key正常分页。服务保存已获结果，但不推进完整成功水位。
Key使用官方支持的Bearer头，避免HTTPX的INFO请求日志输出含Key的URL。已明确的出版社新闻不能被聚合索引笼统的journal-article类型覆盖。

## 数据与兼容

仅扩充来源状态和内容语义，不加表；旧 peer_reviewed 记录继续兼容读取，但新记录使用不夸大审核事实的 journal_article 类型。
Go 的统一内容分栏表达式同时用于查询计数与结果投影：新闻/科研报道优先，预印本次之，再按有效期刊类型；旧 display_kind 不再决定类型。
用户原图中的旧 Phys.org 即刻被读取侧归入新闻；新写入按同一规则保存，不以永久业务数据修补分支替代统一内容规则。

## 组件职责与需求映射

| 需求 | 实现 | 验证 |
|---|---|---|
| FR-001 / US1 | NewsFeed 单入口选择 | 前端重复/非法链接样本、实际页面 |
| FR-002/003 / US2 | Python语义规则与Go统一查询 | 分类、计数、分页及旧记录 |
| FR-004/007 / US3 | publishers 来源目录、RSS与Crossref | 固定夹具与官方端点只读样本 |
| FR-005/006 / US3 | Transport/OpenAlex/collect_source/due | Key、partial、失败隔离 |
| FR-008 / US4 | research 与验证记录 | 项目源码、端点证据及边界 |

## 质量门与阶段

mayuan 分支、明确路径提交；不改其他任务。先记录原话原图与研究，再实现、定向测试、隔离浏览器和只读真实采集。
部署目标未指定，不能把图中的localhost或上次阿里云授权当成本次运行操作授权。文档门按本地/远程实际状态分别记录。
