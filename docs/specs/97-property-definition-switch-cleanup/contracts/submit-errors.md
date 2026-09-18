# 提交错误响应契约

HTTP 400 的模块化物性校验响应保持以下结构：

```json
{
  "detail": "科学数据校验失败",
  "issues": [
    {
      "field": "material_states[0].property_modules[0].records[0].custom_property_key",
      "code": "schema_validation_failed",
      "message": "规范性质不能携带自定义键"
    }
  ]
}
```

`issues` 可以包含多条问题；客户端必须展示全部消息，使用 `field` 与草稿数组结构进行展开、标红和聚焦。服务器不得把完整路径丢失为 `module[...]`。

## 数据库完整性约束错误

提交事务遇到数据库完整性约束时仍返回 HTTP 409，但必须携带可操作的问题：

```json
{
  "detail": {
    "code": "scientific_data_integrity_error",
    "message": "该物性记录的自定义性质身份不完整，请选择自定义性质并填写名称，或清空自定义键",
    "issues": [
      {
        "field": "material_states[0].property_modules[0].records[0].custom_property_key",
        "code": "integrity_constraint",
        "message": "该物性记录的自定义性质身份不完整，请选择自定义性质并填写名称，或清空自定义键"
      }
    ]
  }
}
```

服务端只使用约束分类结果和草稿路径生成消息，不得把 SQL、表名、驱动名、堆栈或数据库内部错误码返回给客户端。若驱动未提供可映射的约束名，`field` 至少为 `material_states` 或 `paper`，消息必须列出用户应检查的字段范围和重新提交动作。
