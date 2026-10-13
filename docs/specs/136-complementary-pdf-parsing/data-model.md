# demo 数据模型

关联 [实施计划](plan.md)。所有对象只保存为 demo JSON，不创建数据库表。

## 输入案例

`case_id` 为文件安全标识；`files[]` 包含 `file_id`、`role`（main/supplementary）、`path`、可选 `sha256`。恰好一份正文；file_id 唯一；源路径相对清单或使用绝对路径。解析前重新算哈希和页数，期望哈希不符立即失败；任何案例内容不能成为通用规则的常量。

## 运行及解析产物

每次生成唯一 `run_id`。`manifest.json` 保存输入身份、实际 Git HEAD、相关代码摘要、版本/配置和阶段结果。每引擎/文件有原始结果、日志、IR、`run.json`，状态为 running/succeeded/failed。失败有阶段、错误类型、退出码/超时和耗时，不含凭据。成功必须可解析原始结果且页面与输入一致。

源 IR 复用 `backend/ingest/document_ir.py`；source_file_id 与 SHA-256 不变。互补 IR 的块仍引用真实原始块 ID，块附原引擎和路由元数据。所有引擎同页几何均转换到 PDF 点；缺坐标明确 null。

## 对齐与冲突

一个对齐组绑定 file_id、PDF 页、基准块及零到多个候选块。记录内容类型、取用理由、主候选、补充候选、空间重叠和不确定原因。不同文本称“解析差异”，只有下游同一科学实体字段冲突才称“字段冲突”；不把空白/LaTeX 写法差异自动认作数值错误。无法唯一对应时保留未匹配，不删除源块。

## 表单与验证

每路结果保存 `paper`、`material_states`、`structure_candidates`、`unmapped_content`、`validation`；状态及记录遵循现有版本 2 草稿/物性定义。原始模型响应与规范化表单分开；校验失败仍可查看候选，但不标通过。证据校验保存实际引用块、页与引句匹配结果；定位成功不等于语义成立。

## 核对与生命周期

核对项 ID 绑定运行、结果臂、字段路径/来源位置；值为 correct/incorrect/missing/not_applicable/unknown，并有 reason、来源和修改时间。页面保存到当前运行的浏览器本地存储，可导出 JSON；导入必须核对 run_id，不能套用旧运行的判断。默认全部 unknown。原始结果只读，重跑创建新目录；无需自动清理用户的历史实验。
