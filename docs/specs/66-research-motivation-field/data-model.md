# 研究驱动力与 AI 理由数据模型

`papers.research_motivation` 是当前论文版本的可编辑文本字段，内容为 1–3 条英文编号动因；没有可靠本文依据时可为空。上传草稿同时在 `paper.research_motivation` 保存当前值，并以 `research_motivation_error` 标记 `source_missing`、`generation_failed`、`invalid_motivation` 等生成失败原因。用户修改正文后，旧错误和旧模型判断不能继续说明当前值。

“AI 理由”不写入 `research_motivation` 正文，也不新建列；现有 `ScientificEvidenceCheck` 与正式 `ScientificEvidenceSource` 的 `item_key`、`content_hash`、`source_hash`、`check_mode=synthesis`、`reason`、`ai_reason` 和 `evidences` 保存当前值的归纳判断与本文引句。上传转论文、返修和批准时沿用版本转接；内容或来源变化后旧理由只作历史，不提供当前支持资格。
