# 数据与来源契约

- 正式值：沿用 `papers.theoretical_subtype`，仅 `calculation`、`method`、`theory`；非理论论文为 `null`。
- 临时分析：服务端草稿保存分类候选、状态、综合理由、代表原文定位、来源摘要、模型与分类规则版本。客户端只能编辑正式字段值，不能伪造分析及支持资格。
- 核对来源：单字段分析与当前值一致且原文定位、全文覆盖条件通过时，`source_kind=paper_synthesis`；否则为待核对/存疑。提交和批准沿用现有 `ScientificEvidenceCheck`、`ScientificEvidenceSource` 与历史转接。
- 用户改值、原文件变化或分类规则变化只使该字段分析与核对失效，不清除其他字段结果。旧草稿缺分析时不把旧 `supported` 解释为新全文归纳资格。
