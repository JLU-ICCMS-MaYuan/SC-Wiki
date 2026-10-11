# 数据与来源契约

## 实体与关系

| 实体 | 字段与身份 | 生命周期 |
|---|---|---|
| 正式论文 | 现有 `papers.theoretical_subtype`；仅理论论文可为 `calculation`、`method`、`theory`，其他类型为空 | 提交后随论文版本保存；本功能不新增业务列 |
| 上传草稿分析 | `theoretical_subtype_assessment` 含 `status`、`value`、`reason`、`evidences`、`source_hash`、`rule_version`、`model`、`covered_batches`、`total_batches` | Worker 或定向脚本生成；Redis 草稿保存，有现有核对时进入 `ScientificUploadDraft` 以供恢复 |
| 字段核对 | `ScientificEvidenceCheck` 中 `target=upload/paper` 与本字段的 `item_key`、内容/来源哈希和规则版本唯一定位 | 当前值或本字段分析变化时产生新身份；旧结果保留历史，不授予当前值支持 |
| 正式来源 | `ScientificEvidenceSource` 按 `paper_id`、`paper_revision`、`item_key` 唯一 | 提交时转接核对与片段文件 ID；批准及后续检索按正式版本读取 |

## 校验与状态转换

1. 理论论文读取当前正文和附件；无来源时 `status=uncertain`、`value=null`。模型异常时 `status=failed`、`value=null`。模型给出有效类别、非空综合理由及可定位的贡献片段时才为 `completed`。
2. 引句最多 3 条且逐字定位到当前文件/片段；至少一条在摘要、结果、讨论或结论。分类器记录来源摘要和读取批次数；引用他人工作不能作为本文贡献。
3. 服务端保留分析对象。浏览器只改 `paper.theoretical_subtype`；当前值与分析候选不一致时分析不能为当前值背书。真实核对还需检查引句及贡献段落，方可为 `supported/paper_synthesis`。
4. 本字段的 `source_hash` 包括分析来源和规则身份。人工改值、原文件变化或规则变化使本字段当前核对失效；其他字段的哈希不随之升版。
5. 定向重跑以原 AI 值、当前值和重读来源摘要作并发保护；未人工修改时可替换旧 AI 值，失败时不沿用旧值。历史草稿无本次分析时，不把旧 `supported` 当作新全文归纳资格。
6. 提交时重新定位引句和文件 ID；若内容或来源不匹配，正式核对回到 `unchecked`。返修草稿不接受客户端回传的分析对象。

## 约束与清理

既有 `ScientificEvidenceCheck` 的唯一键为目标、记录身份、内容/来源哈希和规则版本；正式来源以论文、版本和记录身份唯一。本功能不执行数据迁移、不批量重分历史论文、不清理其他字段核对。上传任务按原生命周期清理；已产生核对的草稿按既有持久化与恢复规则处理。
