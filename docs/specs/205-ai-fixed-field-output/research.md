# 设计与实测

- 复用#203字段清单，避免再维护一套业务字段；提取信封及整理动作仍使用已有协议。
- 不采用静默丢弃未知键：这会掩盖模型没有遵守要求，甚至丢失科学说明。
- 不采用无限重试或额外模型自检：字段结构由接口和本地程序处理。
- 实测当前LLM2 / gpt-6.1-sol：流式strict请求只返回pressure_value_gpa；非法schema返回400 invalid_json_schema。非流式初始探测出现客户端AttributeError，未视为成功，正式入口使用流式。
- 严格输出约束字段名称与形状，不证明数值、压力和物相判断正确；沿用已有理由及人工审核。

- 本地检查使用jsonschema，不调用模型；增加requirements依赖。只对明确传入response_schema的调用启用严格输出。
- 空容器null的有界解码不删除未知键、不改变pressure_value_gpa等科学标量，不影响人工字段。
