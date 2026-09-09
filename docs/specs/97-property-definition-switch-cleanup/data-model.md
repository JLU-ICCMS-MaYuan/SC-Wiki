# 数据模型

## 物性记录身份

| 条件 | `custom_property_key` 结果 | 说明 |
| --- | --- | --- |
| `record_type=property` 且 `property_code=custom` | 非空稳定字符串 | 论文内自定义性质身份，已有值不改；缺失时按 `record_key` 确定性派生 |
| 其他标准记录 | `null` | 包括预测 Tc、测量 Tc 和未来标准物性 |

记录的 `record_key`、`definition_key`、`definition_version`、值字段、`payload`、Evidence 和条件均不因身份清理改变。

## 校验路径

提交草稿中一条记录的规范路径为：

`material_states[状态索引].property_modules[模块索引].records[记录索引].字段名`

模块自身问题使用模块路径，记录问题使用记录路径；路径索引从 0 开始，便于前端与数组直接映射。

## 兼容范围

只处理 `property_modules` 已存在且 schema 版本为 0 或 2 的草稿。传统 `tc_results` / `properties` 转换沿用既有规则；兼容操作深拷贝输入并保持 Evidence 和科学值。
