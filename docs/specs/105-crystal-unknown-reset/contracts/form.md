# 表单与保存契约

## UI

上传 `UploadTaskEditor` 和审核 `AdminPaperEditPage` 共用 `MaterialStatesEditor`。
选择未知（含重复选择、键盘激活）一次发出完整材料状态数组；当前项三字段更新，其他项保留。
空间群符号、编号输入框显示空白，含义为未知；编号不得填 0 或字符串。
只读时不发出修改；加载时不自动清洗；不锁定未知后的空间群输入，允许重新明确填写。

## API

沿用上传草稿 PUT 与科学数据保存 PUT，请求中当前项显式包含：

```json
{"crystal_system":"unknown","reported_space_group_symbol":null,"reported_space_group_number":null}
```

权限、版本校验、错误提示和重试不变。接口不新增“清空”标志；旧客户端和未编辑历史值保持既有语义。
核对监听全部实际改动字段；不绕过已存在的内容版本检查，不启动 AI 或自动批准。
