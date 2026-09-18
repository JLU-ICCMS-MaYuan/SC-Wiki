# 物性记录契约

## 记录身份不变量

```json
{
  "record_type": "measured_tc",
  "property_code": "tc",
  "custom_property_key": null
}
```

```json
{
  "record_type": "property",
  "property_code": "custom",
  "custom_property_key": "custom-property-opaque-id"
}
```

客户端定义切换、前端草稿归一化和后端 v2 草稿兼容层都必须满足上述不变量。权威提交校验仍拒绝标准记录携带非空键，并拒绝缺少自定义键的自定义记录。

## 非破坏性要求

身份清理不得删除或重写 `value_*`、`payload`、`evidences`、`record_key`、定义版本和记录顺序；输出对象必须是输入的独立副本。
