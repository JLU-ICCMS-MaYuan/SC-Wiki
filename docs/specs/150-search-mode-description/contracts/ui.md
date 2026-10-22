# 界面契约：检索方案说明

## 输入与派生

输入沿用 SearchPage 的 mode 与 LanguageContext 的 lang。selected 只影响既有选中元素显示和检索，不决定说明是否显示。

| mode | 名称翻译键 | 说明翻译键 |
| --- | --- | --- |
| elements_combination_search | search.modeCombination | search.modeCombinationDescription |
| elements_exact_search | search.modeExact | search.modeExactDescription |
| elements_contained_search | search.modeContained | search.modeContainedDescription |

## 输出与交互

- 周期表卡片头部第一行：标题、当前说明、三个模式与进入/清除操作，桌面垂直居中。
- 已选元素标签与元素内容置于独立下一行，不参与第一行的高度和中心对齐。
- 标题、模式、进入/清除、已选元素标签与内容统一 16px；说明保留 body2 较小字号。
- 桌面三列网格中标题与操作区为自然宽度，说明占据两者之间剩余宽度，列间距 16px。
- 初始 mode 与既有 URL/默认逻辑一致；按钮点击只更新原 mode。
- mode 变化后说明同步变化；语言切换同步翻译。清除 selected 不清除 mode 或说明。
- 说明区域用可访问的状态文本，模式按钮暴露选中状态并关联说明。
- 1600px 及以上窗口第一行并列；更窄窗口按标题、说明、操作区排列，已选行仍位于其后。不使用截断或固定高度。
- 非三种元素模式时不显示不对应的说明，不新增模式修复或检索行为。

## 错误、权限与兼容

说明无需网络、无新增权限或 API；检索请求的输入、错误和结果行为保持现有约定。示例不代表已收录数据；不修改筛选、排序、数据所有权或持久化状态。
