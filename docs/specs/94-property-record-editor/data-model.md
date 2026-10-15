# 数据模型

不新增表或列。实验条件仍属于本条 property_modules[].records[]，并保存到 property_records.payload_json。

| 字段 | 含义与约束 |
| --- | --- |
| definition_key / definition_version | 保留原始绑定；版本仅从普通标题隐藏 |
| payload.experimental_conditions | 测量 Tc 必须包含对象，与 calculation_conditions 互斥 |
| payload.experimental_conditions.description | 可选自由文本；空字符串有效，非字符串提交应定位报错 |
| 旧六字段及 extensions | 老记录原始信息，展示适配后保留；新文本不重复生成这些字段 |
| record_key | 稳定记录身份；折叠以此绑定，复制生成新键 |

无 description 的历史对象只在读取界面时转换，不在数据库自动改写。
有 description（包括空字符串）时以其为当前显示与编辑文本。
折叠状态只存 React 本地状态，不写入 payload、导出文件或服务器。

Tc 常用输入绑定 value_number；范围绑定 value_min/value_max，单位仍为 canonical_unit=K。
value_raw 和 unit_raw 不再作为独立原始记录：value_raw 从当前数值、范围、文本或布尔生成；
数值/范围 unit_raw=K，文本/布尔 unit_raw=null。输入中的临时非法数字仅保留在界面文本状态，
规范值为 null、value_raw 为空，保存前校验必须阻止提交。空值不能回退到旧数字。
类型切换只清理不匹配的规范值列，record_key、条件及证据保持不变。

## Tc/μ* 配对增量

预测记录继续在 `payload.parameters` 保存 λ (`lambda_ep`)、ωlog (`omega_log`) 和标量 μ* (`mu_star`)；旧 `{value_number,...}` 包装对象仍可读且编辑保留元数据。

范围 μ* 使用既有 `extensions` 数组中的 `{key:"mu_star",value_kind:"range",value_min:0.10,value_max:0.13,unit_raw:"1"}`；主 `mu_star` 不再同时保存。Tc 使用 `value_min=281,value_max=311`，两组为 (281,0.13) 与 (311,0.10)。未知 μ* 端点为 null，不自动补值。有效零值不能视作缺失。

范围的字段键、Evidence 及额外元数据在编辑时保留；其他扩展位置不移动。组件暂存编辑组顺序，以整体配对映射规范端点，数据库不增加组序号。类型切换清理不适用的范围，保留条件和其他参数。测量记录维持实验 Conditions。

## US6～US9 增量契约

参数和计算条件仍保存在原 payload 对象的 extensions，保留 field_key、未知字段、Evidence 和原数组位置。扩展输入非法数字不能变成合法空值。普通性质原始值和规范值契约不变。

热力学使用 payload.thermodynamic_stability={version:1,basis,cases}；各 case 的字段、枚举和温度约束见 Plan。当前 case 必须存在，缺省是 unknown、above_hull=null、ZPE unspecified；无示例数据默认。前后端拒绝无效版本、枚举、非有限/负数、错误单位、非 0 的 ΔE/ΔH 温度及跨模块伪装。value_kind=text、value_raw/value_text 为当前稳定性文本，服务端重新校验一致性。复制时仍生成新记录键。现有 payload_json 和完整导出无损携带全部 cases。
