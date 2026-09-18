# 数据与状态转换

沿用 `DraftMaterialState` / `material_states`，无需新增列或迁移。

| 字段 | 选择未知后的值 | 含义 |
| --- | --- | --- |
| crystal_system | `unknown` | 晶系未知 |
| reported_space_group_symbol | `null` | 报告空间群符号未知 |
| reported_space_group_number | `null` | 报告空间群编号未知 |

三字段属于同一材料状态编辑；state_key、material、结构候选、物性和其他材料状态保持不变。
再次选择未知是幂等操作；只通知实际变化的核对字段。有效空间群重新输入后恢复原联动。
仅渲染已有 unknown + 非空群号时不进行状态转换。保存失败保留编辑对象，成功后仍读到显式空值。
