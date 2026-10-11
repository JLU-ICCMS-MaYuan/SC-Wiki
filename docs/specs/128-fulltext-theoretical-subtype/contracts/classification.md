# 全文理论子类型契约

上传草稿的 `paper.theoretical_subtype` 枚举不变。服务端可返回只读 `theoretical_subtype_assessment`，包含候选值、`completed|uncertain|failed` 状态、简短理由、1–3 条文件/页码/逐字引句及来源/规则/模型身份。PUT 草稿只接受人工编辑的正式值；服务端维持分析所有权。

来源核对结果沿用现有字段路径 `paper.theoretical_subtype`；有效归纳的 `source_kind` 为 `paper_synthesis`，`status=supported` 仍须有可定位且不只来自 Methods 的依据。重跑失败时不得返回旧结果为当前支持。无新增公开提交或审核路由。
