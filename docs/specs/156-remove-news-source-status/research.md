# 设计依据

- 截图区域由 NewsFeed 的 details/summary 与来源列表一次性渲染，整体删除即可。
- SourceState、timestamp、sourceStatus、sourceNeedsAttention 和父组件回调仅供此面板，删除而非 CSS 隐藏。
- 来源目录名称仍被卡片与详情使用，保留；时间精度与原文链接仍属于资讯本身，保留。
- 后端 sources 是现有兼容契约，维持数据库诊断能力；本次不做 API 退役。
- 使用已有前端测试验证行为变化，不增加独立测试框架或配置。
