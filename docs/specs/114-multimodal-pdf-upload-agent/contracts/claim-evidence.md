# Claim 与 Evidence 契约

## Claim

Claim 必须包含 `claim_id`、`target_path`、`value`、`raw_value`、`basis_kind`、`source_kind`、`status`、`confidence` 和 `evidences`。状态为 `validated` 前必须至少有一条可定位 Evidence。

## Evidence

Evidence 必须包含 `file_id`、`source_version`、`pdf_page`、可选 `printed_page`、可选 `block_id`、可选 bbox/polygon、`quote`、`parser` 和 `parser_version`。`quote` 必须能在对应块或 OCR 文本中按规范化规则定位。

## 写入门禁

`paper_quote` 只能来自上传文件；`paper_inference` 仅生成待采用建议；`general_knowledge`、`external_metadata` 和 `external_background` 不得自动写入科学记录。定位失败返回稳定原因并保持草稿/人工状态。
