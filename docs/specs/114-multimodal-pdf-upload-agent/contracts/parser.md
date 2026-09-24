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

## 已实现的本地方案

- `text` → PyMuPDF；`layout` → Docling CPU（文本层、表格）；`ocr` → MinerU basic OCR。
- `vision` 尚未注册；`native_pdf_llm` 仅在显式允许的 OpenAI 文件模型配置下可用。
- 重型 SDK 在与 Worker 相同 Python 环境的独立进程运行。默认超时 300 秒，服务端
  `ParseOptions.parser_options.timeout_seconds` 可设为大于零且不超过 1800 的有限数值。
  超时返回 `parser_timeout` 并终止进程组，不返回部分 IR。
- MinerU 档位参数仅允许 `mineru_tier=flash/basic/standard/advanced`，读取模式仅允许
  `mineru_parse_mode=txt/ocr`；显式选择 flash/txt 时解析元数据必须记录 text。
- 首次运行需要下载模型或事先准备对应缓存；安装成功与模型可用分开判定。
- 模型或依赖失败不返回内部路径、供应商响应、堆栈；主任务仍进入既有 failed 终态。


## 原生 PDF 供应商适配（待真实服务验收）

当前实现 OpenAI Responses 文件输入，读取已安装 SDK 的 input_file 参数契约；仅接受
官方 `https://api.openai.com/v1`，且当前请求模型必须出现在部署配置
`UPLOAD_NATIVE_PDF_MODELS` JSON 列表中。默认列表为空；不根据 OpenAI-compatible 名称
假定支持 PDF。其他供应商需要各自适配。

适配器读取 PDF 页面尺寸作为几何基准，模型只返回文本/区域块，禁止直接返回 Claim。
服务端重新构建 IR、源文件身份和块 ID。限制为 50,000,000 字节、100 页、300 秒、
最多 16000 输出 token；输出未完成或 JSON 不合约时拒绝，不修复截断结果。
请求不注册外部工具，store=false；只保留结构化文档结果，不保存响应中的内部推理。
视觉估读标记不能作为直接论文引句通过 Claim 校验；无法确认表格结构时保留覆盖限制。

本轮接口/拒绝行为使用测试客户端验证，缺少实际供应商凭据，不能宣称真实模型验收通过。
