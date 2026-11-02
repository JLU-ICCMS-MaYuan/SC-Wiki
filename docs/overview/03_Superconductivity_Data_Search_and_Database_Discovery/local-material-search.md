# 本地材料检索

## 功能说明

从元素组合或化学式检索已批准论文、材料状态与完整独立结构。检索结果默认按原始论文展示，可在同一页面右上方切换“按论文／按材料状态”。

## 进入与恢复

网站根路径 `/` 和 SC-Wiki 品牌入口默认进入 `/search` 的检索页面。侧栏探索位于热点之前，热点仍通过 `/news` 访问；默认首页调整见 [Feature #202](../../specs/202-search-default-home/spec.md)。

周期表“进入页面”和化学式“搜索”以新标签页打开结果，保留原标签页的输入和选择。结果地址保存元素／化学式、检索模式、筛选、view及两种视图和独立结构各自的页码。切换展示在当前标签页发生，保留查询条件；浏览器前后退、刷新和详情返回由地址恢复，重新读取最新数据。

元素组合、精确及包含三种模式保留原含义；化学式入口仍按提取到的元素集合匹配，不保证化学计量比严格相等。模式说明及周期表布局沿用[#150](../../specs/150-search-mode-description/spec.md)。

## 查询与展示单位

`POST /api/papers/search/results`由Go直接查询主库，公开范围仅为review_status=approved且approved_revision=content_revision的论文当前版本；登录用户及管理员不会通过公开搜索扩大范围。

- 论文视图：每篇命中论文一项，显示标题、年份、期刊、DOI和匹配状态数。来源集合包含匹配状态及完整结构的来源论文，同一论文不重复。
- 状态视图：每个真实材料状态一项，显示化学式／材料名、压力、报告空间群号／符号和优化方式；同一压力的SSCHA与静态优化分开。同状态的多条Tc或其他物性不增加状态数量。
- 状态身份沿用论文revision下的state_key／id，不按显示字段跨论文合并。没有Tc也能检索；不要求有完整结构才显示状态。
- 匹配与去重在分页前完成，返回papers_total、states_total及当前视图total；默认每页20条。物性只通过相关存在条件限制实际收紧的Tc／图表筛选，不成为默认结果主体。
- 旧搜索Tc明细表和其局部记录详情已退役；正式论文详情与社区Tc图表保留。

## 筛选所有权

压力属于同一个命中状态或结构，年份属于来源论文，关键词匹配材料及论文字段；不能跨状态拼接组成与压力。材料家族筛选查询当前论文revision的paper_material_families与material_families.code，不再把该选项误用为state_kind。

默认数值范围不额外过滤缺失值；实际收紧的Tc／图表条件只限制状态，独立模型不依赖Tc。独立结构请求不随Tc／图表条件或主视图切换重发。公开检索的审核状态不能放宽到待审／拒绝；选择这些状态得到空的公开结果。

## 独立结构与来源

独立区调用Python `POST /api/rag/structural-records/search`并启用independent_only，服务端在计数／分页前排除已关联状态的模型。只有当前已批准revision中retained完整model公开；资料按自身元素匹配，不依赖Tc。

已关联模型在对应状态提供入口，独立伴随模型单列。没有状态的模型不会被虚构为材料状态，但其来源可进入论文视图；收录模型不等于已证实超导。缺原子位置的几何资料不生成完整模型入口。

“查看来源论文”和“查看结构与下载”均新标签打开，保留合法来源地址；结构详情继续提供晶胞切换、三维模型及CIF／POSCAR导出。没有完整模型时不复制其他压强或优化方式的坐标。

## 失败与权限

新结果查询不沿用旧Tc永久缓存。请求失败显示可重试错误，不伪装为0；快速切换或筛选时忽略旧请求响应。详情来源仅接受合法站内地址，直接访问或非法来源使用检索入口兜底，取消固定返回上传列表。

## 实现与验证

- Go：handlers/search_results.go及main.go；Python：backend/api/structural_records.py。
- 前端：SearchPage、SearchResults、searchNavigation及PaperStructuralCollection。
- [#178规格](../../specs/178-search-results-navigation/spec.md)、[验收记录](../../specs/178-search-results-navigation/validation.md)。隔离MySQL与真实React路由浏览器分别验证查询和展示，不表示阿里云或当前原生后端进程已重新发布。
- 结构完整性及保留边界继续见[#49](../../specs/49-pdf-crystal-structure-extraction/spec.md)。本次不重新解析PDF、不改科学数据、模型归属或审核门禁。
