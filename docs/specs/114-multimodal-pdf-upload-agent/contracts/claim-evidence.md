# Claim 与 Evidence 契约

## Claim

Claim 必须包含 `claim_id`、`target_path`、`value`、`raw_value`、`basis_kind`、`source_kind`、`status`、`confidence` 和 `evidences`。状态为 `validated` 前必须至少有一条可定位 Evidence。

## Evidence

Evidence 必须包含 `file_id`、`source_version`、`pdf_page`、可选 `printed_page`、可选 `block_id`、可选 bbox/polygon、`quote`、`parser` 和 `parser_version`。`quote` 必须能在对应块或 OCR 文本中按规范化规则定位。

正式保存时，Evidence 继续写入现有 `paper_evidences`；区域定位通过新增 `paper_evidence_locators` 关联到 `paper_document_blocks`。关联表必须绑定同一 `paper_id + paper_revision + paper_file_id`，不得用前端传入的路径或截图作为身份。

## 写入门禁

`paper_quote` 只能来自上传文件；`paper_inference` 仅生成待采用建议；`general_knowledge`、`external_metadata` 和 `external_background` 不得自动写入科学记录。定位失败返回稳定原因并保持草稿/人工状态。


当前定位检查拒绝空引句、跨文件/版本、假解析器版本、错误来源类别、错误印刷页码、
伪造区域、块缺失和不能唯一匹配的引句。缺省区域只能从同一 IR 的已定位块回填。
`validated` 表示出处定位通过，不替代现有科学语义核对与人工批准。
新 PDF 任务在 reading 结束前保存 Claim/覆盖产物；无法定位或覆盖不足时保留产物并
进入既有 failed 终态、reading_state=needs_review，不伪造 ready。汇总后的科学记录再次
检查出处。TXT/MD 的明确来源仍走现有共享来源校验，不虚构 PDF 页面。

新 IR 转文本时写入服务端块标记，分段/提交定位可用 block_id 区分相同页内的重复引句。
标记只是导航线索，区域证据仍需回到同一 IR 验证；旧文本没有标记时沿用原有规则。
汇总后的已验证出处回填到科学候选，既有单证据/多证据契约保留。
