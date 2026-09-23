# 解析器契约

## 接口

`DocumentParser` 必须暴露 `name`、`version`、`can_parse(source, capabilities)` 和 `parse(source, options)`。`parse` 只返回合法 `DocumentIR` 或稳定 `ParserError`，不得返回 Claim，不得写入论文、物性或审核表。Claim 候选由独立提取步骤读取 IR 后生成，并经过 Evidence 校验。

## 决策

`can_parse` 返回 `supported`、`mode`、`reason`、`required_capabilities` 和所选方案的限制。普通数字 PDF 默认 Docling；复杂页面可选择 MinerU、视觉或 Native PDF LLM IR 方案；PyMuPDF 是可选文本方案。指定方案不可用时返回错误，不在同一次运行中自动切换。

## 错误

错误码至少包括 `parser_dependency_unavailable`、`parser_model_unavailable`、`parser_gpu_unavailable`、`parser_invalid_output`、`parser_timeout`、`parser_unsupported_media` 和 `parser_profile_unavailable`。错误摘要不含堆栈、凭据和服务器路径。

媒体路由必须拒绝把 TXT/MD、CIF/POSCAR 当作 PDF 解析：TXT/MD 使用现有直接读取，CIF/POSCAR 使用 ASE 结构候选流程。

## 兼容

解析器输出必须能转换成统一 IR；旧 Markdown 缓存没有 parser 信息时标记为 `legacy_text`，不能伪装成视觉解析。
