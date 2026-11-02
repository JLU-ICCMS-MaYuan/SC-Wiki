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

## US5 增量设计（取代上文仅本轮“不加表”的限制）

新增 news_feed_candidates 独立候选表及 Alembic 迁移；不向 Go 公开表增加待判记录，保持 API/前端分页契约。候选以 DOI（无 DOI 用 URL）作为稳定身份，持久化规范化 Record 快照和内部摘要/关键词、指纹、状态、模型及尝试信息。

Sources/出版社 RSS 扩大词表，仅作为候选发现；collect_source 将 journal_article 保存为候选，其余新闻/预印本保持原流程。来源 accepted 表示接纳的候选/直接收录条目数，不代表全部已公开。

relevance 模块领取有限批次候选，事务外调用现有 complete_json；related/unrelated/insufficient 为语义结果，pending/running/failed 为任务状态。相同输入与规则不重复；信息不足等待新输入；异常一小时后重试，最多三次；租约过期可恢复。写回核对输入哈希和尝试 token，related 与 upsert 公开条目在同一事务完成。不删除已公开的历史条目，不修改正式科研表。

复用现有资讯调度、RQ 队列和默认模型，每轮最多三条，独立任务避免采集长时间持有事务。按首次进入当前待判版本的时间处理，避免重复发现挤占其他候选。候选不调用全文下载、网页阅读或新建模型服务。

宽泛 hydrogen 检索使用现有分页/请求/任务上限；保留部分结果和 partial，不以首批成功声称完整覆盖。通过跨源相同 DOI 合并、空摘要不覆盖已有非空证据、输入不变复用减少模型调用。不给 Wiley 新建整个出版社抓取系统，通用 Crossref/OpenAlex 支持发现该 DOI。

FR-009→Sources/publishers→T007；FR-010/011→候选模型/relevance→T008；FR-012→状态机/调度→T009；FR-013与SC-005至008→真实样本/隔离迁移/回归→T010；Overview/Issue→T011。


实现细化：Crossref 显式涵盖 superhydrides/polyhydrides 复数；OpenAlex 保留原超导查询优先、另行查氢相关主题，防止无Key的第一批被宽泛查询挤占。相关决定要求可定位原句，引用只有氢体系信息时降为 insufficient。网络请求提前停止，为当前已获候选留出写库时间。候选 JSON 在 MySQL 使用 MEDIUMTEXT；输入之外的来源链接补全不触发重复模型调用。迁移合并两个已提交基线头，不依赖并行任务的未提交迁移。
