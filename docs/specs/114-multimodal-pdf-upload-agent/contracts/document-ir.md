# Document IR 契约

## 顶层字段

`document_id`、`source_file_id`、`source_sha256`、`source_version`、`parse_profile`、`parser`、`pages`、`blocks`、`tables`、`figures`、`formulas` 和 `coverage` 必须可 JSON 序列化。

## 几何

PDF 页码从 1 开始。bbox 为 `[x0, y0, x1, y1]`，必须满足 `x0 <= x1`、`y0 <= y1` 并落在页面尺寸内。polygon 点必须按页面坐标系表达。非法几何只能退回无区域文本证据，并记录定位限制。

## 稳定身份

`block_id` 由 source file/version、解析器版本、解析方案、页码、阅读顺序、类型和内容哈希生成；同一输入重复解析保持稳定。正式块身份以 `parser_run_id + block_id` 区分运行；随机运行编号不参与内容哈希。

## 版本

IR schema、parser version、rule version 和 model version 分开保存；任何一个变化都能使缓存失效并保留旧结果。


## 运行身份归属

解析器返回的是文件内容 IR，不生成数据库主键；正式 parser_run_id 由保存层创建，
通过 ParserRun 行与定位外键关联 IR 快照。任务 IR 不要求携带尚未存在的数据库运行 ID，
旧任务快照因此仍可按原 Schema 读取。
