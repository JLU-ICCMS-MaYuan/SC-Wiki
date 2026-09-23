# 解析器契约

## 接口

`DocumentParser` 必须暴露 `name`、`version`、`can_parse(source, capabilities)` 和 `parse(source, options)`。`parse` 只返回 `DocumentIR` 或稳定 `ParserError`，不得写入论文、物性或审核表。

## 决策

`can_parse` 返回 `supported`、`mode`、`reason`、`fallback_allowed` 和所需能力。普通数字 PDF 默认 Docling；复杂页面可选 MinerU/视觉；不可用时 PyMuPDF。

## 错误

错误码至少包括 `parser_dependency_unavailable`、`parser_model_unavailable`、`parser_gpu_unavailable`、`parser_invalid_output`、`parser_timeout` 和 `parser_unsupported_media`。错误摘要不含堆栈、凭据和服务器路径。

## 兼容

解析器输出必须能转换成统一 IR；旧 Markdown 缓存没有 parser 信息时标记为 `legacy_text`，不能伪装成视觉解析。
