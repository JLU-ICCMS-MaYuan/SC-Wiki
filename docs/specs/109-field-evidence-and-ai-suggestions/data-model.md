# 数据与生命周期

复用 `scientific_evidence_checks.result/resolutions`、`scientific_upload_drafts` 和 `scientific_evidence_sources.result`，无需新增数据库表。

- 字段身份沿用 `item_key`、`state_key`、`module_key`、`record_key`、结构哈希；数组下标仅用于展示定位。
- 核对项增加 `required`：当前是否有需核对的断言；空可选项为 false，仅展示/建议，不产生提交门禁。字段清单允许无值项目，字段类型不能从 null 推测，使用已知定义。
- 建议在 `proposal` 增加 `basis_kind`（`paper_quote`、`paper_inference`、`general_knowledge`）和 `explanation`。保留类型化 `values`、`evidences`、`supported` 与版本绑定。后两类不能标为直接支持；通用知识可没有引句。
- 采用决定保留建议依据、原值、最终值、操作者、理由及内容/来源摘要。`adopted_basis` 保存已采用的来源性质，不因后续 AI 复核或人工批准消失。
- 核对结果可保留 `proposal_review` 表达对已有建议的合理性判断，与当前值的支持状态分开。
- 上传建议和核对结果持久保存，提交转接稳定身份。批准复制到永久来源后清理临时核对；旧结果仍可读但不得用于新值批准。
- 空记录和未采用建议必须同样转接/归档，不能因不属于提交门禁而在批准时丢失。
- 旧无新增字段的结果按原文建议处理；没有依据标签的历史人工决定保持人工来源，不推定为通用推测。规则版本更新使需要重核的结果失效，不批量写历史。

历史使用 `history` JSON 列表，存放旧当前值、建议、引用、判断与人工理由，跟随上传转接及 Go 永久归档。来源或内容不匹配的历史不授予当前确认资格。后台复核撤回旧支持资格时，未提交接受草稿恢复 `accepted=false`，保留输入；已完成的人工决定只由明确人工保存更新。
