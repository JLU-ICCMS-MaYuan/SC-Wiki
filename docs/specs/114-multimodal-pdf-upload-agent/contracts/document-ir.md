# Document IR 契约

## 顶层字段

`document_id`、`source_file_id`、`source_sha256`、`source_version`、`parser`、`pages`、`blocks`、`tables`、`figures`、`formulas` 和 `coverage` 必须可 JSON 序列化。

## 几何

PDF 页码从 1 开始。bbox 为 `[x0, y0, x1, y1]`，必须满足 `x0 <= x1`、`y0 <= y1` 并落在页面尺寸内。polygon 点必须按页面坐标系表达。非法几何只允许降级为无区域文本证据。

## 稳定身份

`block_id` 由 source file/version、页码、阅读顺序、类型和内容哈希生成；同一输入和解析器版本重复解析必须保持稳定。

## 版本

IR schema、parser version、rule version 和 model version 分开保存；任何一个变化都能使缓存失效并保留旧结果。
