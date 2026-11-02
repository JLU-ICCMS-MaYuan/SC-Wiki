# 采集方案研究与实测（2026-10-23）

## 已确认的当前问题

图2数据的两个URL均为 https://phys.org/news/2026-10-hidden-rivalry-quantum-states-heart.html，
只区分 discovery/original；前端还以source作重复key。当天普通HTTP请求返回200，重复展示可证实，
“第一条URL失效”不能作为已证实事实。旧 #88 明文要求 Phys.org 放入期刊栏，本次新需求废止此例外。

OpenAlex按现有采集器执行完整调用：第一页200、第二页401，fetched=100后整个来源失败。
[当前认证文档](https://developers.openalex.org/how-to-use-the-api/rate-limits-and-authentication)明确基本查询可无Key，
后续游标分页需要免费Key，免费Key提高每日预算；这不是“所有API都需要注册”，也不是Cloudflare全站阻断。
不代用户申请Key，支持可选配置并将无Key结果标为部分完成。

Crossref当前只有superconduct词根；NSR全时期的superconductivity控制查询可得26条，superconducting可得30条，
不能用词根查询返回零推断期刊没有论文。期刊DOI片段prefix:10.1093/nsr的控制查询返回了其他注册前缀的论文，
不能将其当作期刊范围保证；正确使用ISSN并逐条校验。以上是不同查询的控制样本，不是最新周覆盖率统计。

首次候选实测仍按索引日期过滤，结果出现2001年的重新索引论文；已改为发表日期窗口。
候选方案曾尝试published排序+cursor，Crossref实际返回400，明确这组组合不支持；最终用发表日期过滤、indexed排序+cursor，列表仍按发表日期排列。该400是本轮候选方案发现的问题，不冒充旧版本故障。

OpenAlex文档确认Bearer头和api_key查询参数等价，最终采用Bearer避免请求URL日志泄露Key。
后续匿名实测返回429，响应明确表示共享出口IP的免费日额度已耗尽；停止继续探测该API，不尝试更换出口绕过额度。
这进一步说明Key用于独立身份/预算与分页，不代表所有期刊源必须注册。

Phys.org链接初次普通HTTP探测200；后续自动化Chrome得到400，常规Chrome出现连接检查且等待30秒未取得正文。
因此仅确认当前两条链接是同一URL，应用中的重复入口已修正；外站正文直达尚不能宣布通过，已请用户在其普通浏览器复核。
不能把这次外站限制直接归因为用户最初“第一条链接不能用”的原因。

## 官方入口实测

| 入口 | 结果 | 采用边界 |
|---|---|---|
| https://feeds.aps.org/rss/recent/prl.xml 、prb.xml | 200，均100条，PRB有超导相关题名 | 使用元数据/原链接，不转载许可不明的全文 |
| https://www.nature.com/nature.rss | 200，75条，含新闻 | 按实际内容类型区分；d41586新闻不能归期刊研究 |
| https://www.nature.com/nphys.rss | 200，含2026-10-20至22的超导相关研究 | 采用；nmat/ncomms也能解析，不代表当前窗口必有超导论文 |
| https://www.science.org/action/showFeed?type=etoc&feed=rss&jc=science | 200，41条 | 依据dc_type区分内容 |
| https://www.science.org/action/showFeed?type=axatoc&feed=rss&jc=science | 200，10条，样本日期较旧 | 提前发表源不保证比当期源更新，两者与索引补充 |
| https://rss.sciencedirect.com/publication/science/13697021 | 200，23条 | 有的仅月份，保留精度，不伪造日 |
| ACS showFeed / NSR主页 | 当前403 | 记录入口受限，使用索引补充，不报官方RSS成功 |
| 猜测的CPL/CPB旧RSS、NSR旧feed | 404或HTML，不是有效RSS | 不把猜测地址加入默认成功来源 |

[Crossref使用建议](https://www.crossref.org/documentation/retrieve-metadata/rest-api/tips-for-using-the-crossref-rest-api/)：
遵守限流、限定分页时间窗口，提供联系信息可使用polite池；免费Key并不是修复所有采集失败的通用前提。

## 开源项目对比

| 项目 | 实际能力与源码依据 | 本次选择 |
|---|---|---|
| [RSSHub](https://github.com/DIYgod/RSSHub) | Nature research、ACS journal、Science early、OUP journals专用路由；ACS使用Playwright加载目录 | 参考来源适配与缓存分层；本次优先官方RSS，不复制AGPL源码到项目或部署整套服务 |
| [RSS-Bridge](https://github.com/RSS-Bridge/rss-bridge) | 将没有RSS的网站转换为RSS，存在ElsevierBridge | 适合以后补站点桥接，不自动解决来源真实性与更新覆盖 |
| [Scrapy](https://github.com/scrapy/scrapy) | 成熟的请求、调度、解析和重试框架 | 现有RQ/HTTPX已承担这些职责，本次不重复引入 |
| [Crawlee](https://github.com/apify/crawlee) / [Crawl4AI](https://github.com/unclecode/crawl4ai) | 浏览器渲染、会话、动态内容抽取等能力 | 静态RSS/API可用时不需要重浏览器；不能保证所有挑战页可过 |
| [FlareSolverr](https://github.com/FlareSolverr/FlareSolverr) | 浏览器辅助处理部分Cloudflare挑战，需要额外服务 | 不能解决API缺Key、错误查询或内容误分，当前不作为默认依赖 |

具体已读源码：
[ACS](https://github.com/DIYgod/RSSHub/blob/master/lib/routes/acs/journal.tsx)、
[Nature](https://github.com/DIYgod/RSSHub/blob/master/lib/routes/nature/research.ts)、
[Science](https://github.com/DIYgod/RSSHub/blob/master/lib/routes/science/early.ts)、
[OUP](https://github.com/DIYgod/RSSHub/blob/master/lib/routes/oup/index.tsx)。

AI日报系统通常也是定时任务、多个来源适配、缓存去重和内容筛选的组合；不能因存在开源项目就宣称任意期刊都可完整抓取。


## 2026-11-02 富氢候选与模型判断

直接 Crossref DOI 接口可取得 10.1002/anie.8236450 的题名摘要（公开返回的摘要缺少部分公式，不能填造）；旧筛选返回空依据。2026-10-03 至 11-02 的真实查询中，superhydride 单数返回0条，superhydrides 复数返回3条并命中该 DOI，故显式查询单复数；不能假设上游自动词干化。新增候选保留这些结果，来源不是 Wiley 官方全文抓取。

已有公开表由 Go 直接查询，若把待判条目混入公开表需要改所有分页/计数路径。因此选择独立候选表，让公开契约不变；不采用“先发布、模型后删”方案。内部 Record 携带 screening_abstract/screening_keywords，不向公开 Item 或 API 增加这些字段。记录采用 MySQL MEDIUMTEXT，防止多字节摘要和多源元数据超过 TEXT 容量。

模型首次真实测试将仅描述高压超氢化物的摘要猜成 related（证据见 relevance-live-model-initial.json）。修正提示并要求 related/unrelated 给出输入的逐字引用；related 引用没有超导或配对上下文时降为 insufficient，保留原决定用于审计。这是防止无依据发布的保守出口，不是重新丢弃候选。改后七例通过，其中一例是真实 Crossref 论文，六例是合成边界；不等于分类全覆盖准确性保证。

既有默认 LLM 配置、RQ 队列、事务 upsert 和研究类型标签均复用；候选判断单独短任务，没有新增运行服务或前端筛选。公开新闻/预印本不扩展氢词范围，避免超出本次期刊需求。业务库变更与历史回填等待明确目标，不将本次隔离迁移当作上线。

已提交基线 dcd07a29 的 Alembic 有 20261020_0049 和 20261101_0198 两个头；本迁移将其合并并仅新增候选表。并行 #203/#204 的未提交迁移另有分支头，不纳入本次提交；组合部署前需按最终提交图协调迁移合流。
