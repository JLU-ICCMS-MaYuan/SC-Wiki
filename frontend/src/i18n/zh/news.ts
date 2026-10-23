// 快讯域文案：首页快讯 Hero、自动采集信息流（NewsFeed）、来源状态、详情抽屉与人工快讯（ManualNews）。
// 通用按钮（重试等）复用 common 域；仅此页专有的文案放在这里。
export default {
  currentWeek: '本周 · 北京时间周一 {start} 起',
  historyScope: '其他已收录内容 · 按发表时间从新到旧',
  moreHistory: '历史更多',
  backToWeek: '返回本周',
  classificationNotice: '标签依据标题和摘要自动判断',
  moreFamilies: '另有 {count} 个材料家族，点击条目查看全部',

  // Hero 区
  heroAffiliation: '吉林大学 物理学院 物质模拟方法与软件教育部重点实验室',
  heroTitle: '超导维基',
  heroSubtitle: '面向超导研究的 AI 驱动去中心化科研数据基础设施，融合可追溯科学数据、Tc 预测、超导知识图谱与 RAG 智能问答。',
  startExploring: '开始探索',

  // 诺贝尔奖里程碑
  nobelMilestones: '诺贝尔奖里程碑',


  // 信息流
  feedTitle: '超导快讯与最新论文',
  feedSubtitle: '官方来源每日采集 · 按发表时间排序',
  kindNews: '新闻',
  kindPreprint: '预印本',
  kindJournalArticle: '期刊论文',
  kindResearchReport: '科研报道',
  feedNewsColumn: '新闻',
  feedPreprintsColumn: '预印本',
  feedArticlesColumn: '期刊论文',
  autoCollected: '自动采集，未经本站审核',
  loadingFeed: '正在加载资讯…',
  feedLoadFailed: '资讯读取失败，请重试。此状态不代表没有新闻。',
  feedEmpty: '当前筛选下暂无资讯',
  weekEmptyHint: '本周暂无已收录内容，可通过“历史更多”查看其他条目。',
  historyEmptyHint: '暂无已收录的历史内容。',
  publishedAt: '发表：{date}',
  publishedLabel: '发表：',
  etAl: ' 等',
  pageInfo: '共 {total} 条 · 第 {page} / {pages} 页',
  prevPage: '上一页',
  nextPage: '下一页',

  // 详情抽屉
  authorLabel: '作者：',
  journalLabel: '期刊：',
  sourceLabel: '来源：',
  originalSourceLabel: '原文来源：',
  relevanceLabel: '命中依据：',
  versionLabel: '版本：',
  collectedLabel: '采集：',
  summaryLabel: '摘要',
  summarySourceLabel: '摘要来源：',
  doiLabel: 'DOI：',
  originalLinks: '原文链接',

  // 日期显示
  dateNotProvided: '日期未提供',
  yearOnly: '{year} 年',
  monthOnly: '{month}（仅提供月份）',

  // 人工快讯
  manualTitle: '人工快讯',
  loadingManual: '正在加载人工快讯…',
  retryManual: '重试人工快讯',
  manualLoadFailed: '人工快讯读取失败',
  manualEmpty: '暂无人工发布的快讯。',
} as const
