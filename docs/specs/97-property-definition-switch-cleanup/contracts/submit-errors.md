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
