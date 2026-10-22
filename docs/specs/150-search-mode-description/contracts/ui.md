# 界面契约：检索方案说明

## 输入与派生

输入沿用 SearchPage 的 mode 与 LanguageContext 的 lang。selected 只影响既有选中元素显示和检索，不决定说明是否显示。

| mode | 名称翻译键 | 说明翻译键 |
| --- | --- | --- |
| elements_combination_search | search.modeCombination | search.modeCombinationDescription |
| elements_exact_search | search.modeExact | search.modeExactDescription |
| elements_contained_search | search.modeContained | search.modeContainedDescription |

## 输出与交互

- 周期表卡片头部：标题及已选元素、当前说明、三个模式与进入/清除操作。
- 初始 mode 与既有 URL/默认逻辑一致；按钮点击只更新原 mode。
- mode 变化后说明同步变化；语言切换同步翻译。清除 selected 不清除 mode 或说明。
- 说明区域用可访问的状态文本，模式按钮暴露选中状态并关联说明。
- 桌面并列展示；空间不足时自然换行，不使用截断或固定高度。
- 非三种元素模式时不显示不对应的说明，不新增模式修复或检索行为。

## 错误、权限与兼容

说明无需网络、无新增权限或 API；检索请求的输入、错误和结果行为保持现有约定。示例不代表已收录数据；不修改筛选、排序、数据所有权或持久化状态。
