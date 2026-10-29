# 数据模型

沿用 material_states → property_modules → records。材料、压力、物相、结构优化由既有状态持有；整理不能跨状态复制数据。

模型输出的结果引用输入 candidate_id；一个候选可对应多个配对点，多个重复候选可对应同一结果。每个候选最终属于输出结果、明确排除或未解决之一，禁止重复分类。每个结果有来源编号，服务器回填原文、页码和块，模型不重抄引句。

共同参数组、方法行和结果点使用既有 payload.tc_group；group_key、method_key、point_key 由服务器生成，不以数组显示位置作为持久身份。method_code 使用现有枚举；other 名称保存 method_raw。参数与条件仍在原 payload，不新增同义 μ* 扩展。

整理报告保存契约版本、输入摘要、原始响应、已读来源、候选映射、补全说明和停止原因。它是解析证据，不替代 GitHub Issue 的工作状态，也不构成人工审核决定。
