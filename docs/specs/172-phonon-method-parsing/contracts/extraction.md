# 新提取条件契约

1. calculation_conditions 缺失或 null 表示没有候选；非空非对象拒绝。
2. extensions 主格式是对象数组；每项 key 为非空字符串，其他既有元数据保留。
3. null、{} 可整理为 []；仅精确的 {"electron_phonon":{"phonon_method":"DFPT"}} 形状可转换。方法必须非空文本，原值不改写；未知或混合对象明确 ValueError，不静默删除。
4. 整理先于方法校验和原文过滤，不放宽证据、科学值及来源规则。
5. 显示“声子方法”，内部 key 不变；人工显式 name_raw 优先。
6. 不增加现有重试次数；格式错误沿用当前错误处理，不将异常当成成功。

7. 已知计算条件不能使用无阶段的扩展 key（如 exchange_correlation_functional）；应使用固定字段或 stage.parameter，以免绕过原文和软件归属检查。陌生自定义 key 保留，不擅自推断其科学语义。
