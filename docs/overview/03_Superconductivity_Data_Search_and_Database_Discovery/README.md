# 超导数据搜索与数据库发现

## 功能边界

该功能负责从元素组合、化学式和超导体记录出发查询本地论文与物性数据，提供默认论文／同页材料状态双视图、来源与完整结构新标签阅读、离线导出和 Tc 统计图表。当前前端入口是 `/search` 与 `/share/charts`（旧 `/share` 重定向至图表）。它不负责修改权威数据、审核论文或摄入 RAG 文档。

## 小功能目录

| 小功能 | 职责 | 依赖 |
| --- | --- | --- |
| [本地材料检索](local-material-search.md) | 按化学式或元素关系匹配论文、材料状态与完整独立结构 | Go／Python API、MySQL、`property_records`、`material_states`、`paper_structural_records` |
| [论文与物性结果](paper-and-property-results.md) | 组织论文、关键物性、结构预览和搜索结果 | 本地材料检索、论文关系 |
| [分享与导出](share-and-export.md) | 输出 JSON、RIS 等分享数据 | 论文与物性结果 |
| [代表结构查询与下载](representative-query-and-download.md) | 匹配超导记录、选取代表结构并控制下载 | 已批准结构、访问权限 |
| [Tc 历史与压力图表](tc-history-and-pressure-charts.md) | 生成并展示 Tc-year 与 P-Tc 数据，两图保持 4:3 并适配窗口 | `property_records`、`material_states`、`material_families`、Recharts |

## 功能组成

```text
超导数据搜索与数据库发现
├── 本地材料检索
├── 论文与物性结果
├── 分享与导出
├── 代表结构查询与下载
└── Tc 历史与压力图表
```

## 关联关系

用户从 `/search` 的周期表或化学式输入进入检索。检索经 Go API 查询 `chemical_systems`、`superconductors`、`property_records`、`material_states` 和 `papers`。`/share/charts` 使用 Recharts 绘制 Tc-Pressure 与 Tc-Year 图表，按材料家族筛选；图表组合的编辑入口在管理页。01 上传并审核通过的论文是本地检索结果的事实来源之一。论文／结构详情按合法来源返回检索，社区评论和体系讨论入口已退役；[AI学术讨论](../06_Researcher_Community_Forum/community-discussion.md)保留问题、答案和来源引用，不修改科学记录。
