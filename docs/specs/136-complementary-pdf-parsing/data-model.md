# 四工具数据模型

关联 [实施计划](plan.md)。历史 demo 对象保留为 JSON；正式流程复用现有数据库表，不新增表或迁移。

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

## 正式互补 IR 与题录

parse_profile=complementary，parser.name=complementary；components 保留每个解析器实际版本。blocks 保留全部原始块，metadata.source_parser/source_parser_version/source_kind 标原始来源；selected_for_reading 控制模型读取与覆盖审核，不能把未选块当作未处理错误。表格跨度在单元 metadata，缺坐标保留 null 和 capability_limitations。

coverage.routing 保存原始锚点、页、所选块/文字/引擎、理由及 alternatives；component_runs 标实际请求页与 not_needed/failed/succeeded，grobid 保存题录、XPath/坐标、参考文献和正文引文目标。页面几何一致时才合并，不跨文件或版本。

任务制品以文件和 UUID 分运行保存原始输出与日志；科学提取以 extraction_attempts 保存输入、响应和失败原文。缓存签名包含方案、输入、模型端点、提示和 thinking 策略。

## 科学引用与参数

模型既可返回逐字 quote，也可显式返回 quote_id=block_id、quote=null。后者只在本次输入的 (file_id, pdf_page, block_id) 原文映射中解析，服务器展开真实完整文字。无原文映射、身份不符或同时提供改写 quote 时拒绝。引用块不证明科学语义，逐条物性/条件核对仍执行。

lambda_ep/omega_log/mu_star 接受合法标量；范围不取端点，放入 parameters.extensions 的 value_min/value_max/value_raw/unit_raw，移除该参数主标量键。Tc 记录压力与状态压力矛盾或明确引句压力错挂时拒绝。
缺少状态压力但原文明确写出当前数值的“值 + K/eV + at/@ + GPa”时，确定性按该压力拆分记录，保留 `_pressure_bindings` 的原状态索引、原 pressure_raw、规则版本和来源块。不会从稳定区间、相名或他条记录推测测量压力；已有明确状态压力冲突仍拒绝。

## 现有持久化

正式提交在现有论文事务保存 paper_document_parser_runs.document_json、paper_document_blocks、paper_evidence_locators 和引用提取表。source_file_id/grobid.file_id 绑定正式 paper_files.id，uploaded_file_id 保留上传身份。原块 ID 不变，位置由服务器再次验证文件哈希、论文版本与原文。bibliography_sources/conflicts 与 parsing_conflicts 留在审核制品；浏览器保存不能覆盖服务器来源。
