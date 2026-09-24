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

## 版本化领域提取

新 PDF 读取使用 `extraction_version=1`，输入为连续页的完整 IR 块、几何和表格单元，
按大小预算打包；可容纳时重叠前一页，支持跨页条件。单页超过预算明确失败，不截断
后假称已读。TXT/MD 保留原文本提取，结构附件继续使用 ASE。

模型返回 `material_states[].property_modules[].records[]`，直接遵循现有模块化科学
契约，不通过 `tc_results` 中转。材料、压力与范围、实验/理论类别、方法、判据、条件、
原始值/单位、不确定度及多条证据分别保存。未知方法保持 unknown，不从 experimental
猜成 resistivity。模型不生成数据库身份，记录键和定义绑定由服务端生成；最终提交
仍检查正式表单定义。每条来源必须引用本次输入的 file_id、pdf_page、block_id 和 quote。

全文汇总只生成书目、分类与叙述；科学记录由后端从已校验候选确定性组装。只有状态
属性完全相同才合并状态，记录连同条件和来源完全相同时才去重；不靠全文 LLM 改写
或补齐科学值。直接提取、IR 定位及最终提交的语义审核属于不同校验层。
