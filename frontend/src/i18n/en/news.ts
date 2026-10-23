// 英文快讯域文案。键集必须与 zh/news.ts 完全一致——字典类型由中文侧推导，
// 缺键会在 `tsc -b` 阶段报错，不会静默回退。
export default {
  currentWeek: 'This week · from Monday {start} (UTC+8)',
  historyScope: 'Other collected items · newest first',
  moreHistory: 'More history',
  backToWeek: 'Back to this week',
  classificationNotice: 'Labels are inferred automatically from titles and abstracts',
  moreFamilies: '{count} more material families; open the item to view all',

  // Hero
  heroAffiliation: 'Key Laboratory of Material Simulation Methods & Software of Ministry of Education, College of Physics, Jilin University, China',
  heroTitle: 'Superconduct Wiki',
  heroSubtitle: 'An AI-driven, decentralized research infrastructure for superconductivity, unifying curated scientific data, Tc prediction, a superconductivity knowledge graph, and retrieval-augmented AI assistance.',
  startExploring: 'Start Exploring',

  // Nobel milestones
  nobelMilestones: 'Nobel Prize Milestones',


  // Feed
  feedTitle: 'Superconductivity News & Latest Papers',
  feedSubtitle: 'Collected daily from official sources · Sorted by publication date',
  kindNews: 'News',
  kindPreprint: 'Preprint',
  kindJournalArticle: 'Journal article',
  kindResearchReport: 'Research report',
  feedNewsColumn: 'News',
  feedPreprintsColumn: 'Preprints',
  feedArticlesColumn: 'Articles',
  autoCollected: 'Auto-collected, not reviewed by this site',
  loadingFeed: 'Loading news…',
  feedLoadFailed: 'Failed to load the feed. Please retry. This does not mean there is no news.',
  feedEmpty: 'No news matches the current filter',
  feedEmptyHint: 'Try a different content type, or check whether the sources below have been collected successfully.',
  publishedAt: 'Published: {date}',
  publishedLabel: 'Published: ',
  etAl: ' et al.',
  pageInfo: '{total} items · Page {page} / {pages}',
  prevPage: 'Previous',
  nextPage: 'Next',

  // Detail drawer
  authorLabel: 'Authors: ',
  journalLabel: 'Journal: ',
  sourceLabel: 'Source: ',
  originalSourceLabel: 'Original source: ',
  relevanceLabel: 'Match evidence: ',
  versionLabel: 'Version: ',
  collectedLabel: 'Collected: ',
  summaryLabel: 'Abstract',
  summarySourceLabel: 'Abstract source: ',
  doiLabel: 'DOI: ',
  originalLinks: 'Original links',

  // Date display
  dateNotProvided: 'Date not provided',
  yearOnly: '{year}',
  monthOnly: '{month} (month only)',

  // Manual news
  manualTitle: 'Manual News',
  loadingManual: 'Loading manual news…',
  retryManual: 'Retry manual news',
  manualLoadFailed: 'Failed to load manual news',
  manualEmpty: 'No manual news has been published yet.',
} as const
