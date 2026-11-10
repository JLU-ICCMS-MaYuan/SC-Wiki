# 数据与状态

沿用工作稿、ScientificManualEvidence、ScientificEvidenceCheck/Source、PaperHistoryEvent，不新增表和标准科学字段。

- field_decision：既有contract/action/actor/hash，新增mode=without_evidence；表示当前值人工无证放行，check_method=human、ai_reason为空、evidences为空。持久状态仍supported但展示warning，不能声称模型核对。
- manual_evidence_provided：当前值资料已有reason和至少一份真实items；只读派生能力元数据，不进入整稿科学内容判等。完整补证使without_evidence失效；材料状态/值/来源变化仍按原合同失效。
- 人工项url/image/pdf/text各自条数校验；url保存地址与稳定摘要，读取内容/回执和地址分开。文字单项，旧text_file保留兼容读取。
- 颜色仅见#220；交互仅见#221。旧empty决定保留原版本语义，不能改写旧快照。
