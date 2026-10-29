# 数据契约

## 结果计算条件

每条物性继续持有 payload.calculation_conditions：

| 字段 | 含义 |
| --- | --- |
| electronic_method | DFT、HF、DFT+U等电子理论；软件、泛函、DFPT和harmonic不属于此栏 |
| phonon_method | DFPT、有限位移、SSCHA等实际响应/声子技术，可表达复合流程 |
| vibrational_treatment | harmonic、quasi_harmonic、anharmonic_quantum、anharmonic_classical或未说明 |
| method_scope | physical_object、stage、workflow_id；电子性质的振动修正另含relation及relation_evidences |
| calculation_code / exchange_correlation_functional | 沿用软件及泛函字段，不从其他阶段推断 |
| extensions | 其他阶段的 stage.parameter、原报告值及稳定 field_key，复用现有来源关联 |

条件属于当前记录；只在原文明确适用同一材料/相/压力/方法/阶段时共用。电子性质若没有明确电子—声子修正关系，不接收phonon_method或vibrational_treatment。已确认关联使用原有内容/来源绑定，不新增批准身份。

## 状态结构优化

structure_optimization 的新目标为 unknown、classical_static、quasi_harmonic、anharmonic_quantum；旧 sscha 保留可读且不自动转换。structure_optimization_details 保存 method、electronic_method、calculation_code、temperature_k、pressure_gpa、centroids、volume、cell_shape；后三项取 fixed/optimized/unknown。不把未报告的自由度补成optimized。来源继续用 state.field_evidence 的对应字段路径，不复制科学主值。

可空JSON列避免给旧记录制造内容；新目标约束支持旧sscha但新提取只要求四类物理目标。物性payload无数据库列迁移。旧approximation保持可追溯，读取零写入；不执行批量修复。
