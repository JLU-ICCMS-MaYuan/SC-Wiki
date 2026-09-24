# Rollout 契约

## 阶段

- `legacy`：仅旧链路。
- `shadow`：旧链路结果服务用户，新链路只保存对照结果。
- `gray`：按允许名单/比例启用新链路；新链路失败时任务可以显式回到旧链路，但不会在解析器内部静默切换方案。
- `default`：新链路默认；任务仍可显式选择已支持的解析方案，旧链路保留为任务级回退。

## 门禁

默认切换必须有 50 篇评测报告，满足 SC-001～SC-003，且失败收敛和旧缓存回归通过。配置不满足门禁时拒绝进入 `default`。解析方案通过任务策略选择并记录；不要求用户长期绑定某个解析器。

## 观测

每次运行记录主阶段、`reading` 子状态、解析方案、解析器、版本、错误码、耗时、token/资源统计和最终路径；不记录密钥或思维链。

## 默认切换报告

`UPLOAD_PARSER_QUALITY_REPORT` 指向维护者提供的本地 JSON 报告。当前检查字段为：

- `annotated_papers`：人工标注论文数，至少 50。
- `new_f1`、`legacy_f1`：新链路不低于旧链路。
- `new_complex_recall`、`legacy_complex_recall`：复杂样本召回率必须提升。
- `evidence_location_rate`：至少 0.95。
- `unsupported_writes`：整数 0。
- `failure_recovery_passed`、`legacy_revision_review_passed`：必须为 true。

缺项、非有限数值或不满足门槛时拒绝 default；未知 rollout 配置也报错，不静默换模式。
显式选择 legacy 的任务不受维护者默认方案覆盖。

报告必须具有 `benchmark_version: "1"`、人工集标记、四个输入摘要、全部类别样本数、
新旧逐论文计数、逐类别指标及独立验收引用。只提供上述汇总字段的早期报告不再接受。
配置检查重算逐论文总计，核对新旧论文集合与分母；扫描、多页表格、多压力必须分别
提升，不能用复杂总计抵消单类退步。

通过 `python -m backend.ingest.pdf_benchmark` 生成报告；格式和口径见
[评测说明](../../../../tests/fixtures/issue114/README.md)。合成集不计人工论文数，
未实测资源保留 null。真实标注集、完整上传运行驱动与输出导出仍未完成，T002/T030
保持未完成；维护者仍须审核输入与独立验收真实性。
