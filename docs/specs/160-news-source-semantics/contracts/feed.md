# 接口与任务约定

列表参数与排序按 [#153 最新契约](../../153-news-classification-labels/contracts/feed.md) 执行：2026-11-02 已取消自然周锚点，按发表时间倒序连续分页。分类标签与links数组保留。kind和display_kind均按内容语义投影；
新闻报道不会进入journal_article总数。原文详情只渲染一个safe URL，后台多来源信息不删除。

来源状态partial表示取得并保存部分有效内容，但至少一个入口或后续页未完成。
last_success_at仅在完整采集成功时前移；partial与failed按一小时重试，不逐分钟空转。
NEWS_OPENALEX_API_KEY为可选私有配置，不回传或记录在错误日志中。


## 收录前候选补充契约

期刊候选位于 news_feed_candidates，GET /api/news/feed 仍仅查询 news_feed_items，公开列表的计数与标签形状不变；时间范围以 #153 最新契约为准。内部 screening_abstract/screening_keywords 不进入 API。source.accepted 包含已接纳候选，不等于已公开期刊数。只有 related 的写回事务调用既有 upsert；unrelated、insufficient、pending、running、failed 均不能作为新公开条目返回。

相关性任务 scwiki-news-relevance 在原 scwiki-news 队列运行，最多三条/批；任务超时240秒、租约300秒、失败重试间隔一小时、最多三次。数据库写入失败使发布和语义决定共同回滚；过期运行记录可以恢复。输入变化清除旧尝试并重新待判，相同输入/规则的三个语义结果不重跑。
