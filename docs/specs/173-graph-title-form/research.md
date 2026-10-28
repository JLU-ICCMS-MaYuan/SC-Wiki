# 调查与设计决定

1. **故障类别：主路径表单接入缺失。** 后端 `scientific_evidence.PAPER_FIELDS` 已有该字段，`upload_jobs._normalize_draft` 保留字段；前端 `UploadTaskEditor` 与 `PaperDraftFields` 未声明入口。不能用删除核对记录作为修复。
2. **复用 ReviewPaperTextField。** 它已连接主表单和字段设置，支持只读及侧栏并发值检查。另建普通 TextField 会漏掉侧栏编辑能力。
3. **复用 setPaperField 与现有保存器。** 字段变更通知核对结果失效；`fieldChanges` 只发送精确路径，`createFieldDraftSaver` 获取版本后 PATCH。不得另建整篇覆盖接口。
4. **保持值所有权。** `normalizePaperFields` 展开原 paper 对象，后端草稿已支持该字段。本次增加类型声明，不生成值或以原标题替代真实空值。
5. **名称与用途。** 表单使用与核对一致的“图谱科学标题”，辅助文本说明用途并显示完整键名；英文 UI 有对应文案，内容不随界面语言转换。
6. **验证边界。** 真实 React 宿主测试验证控件与保存器的联接；浏览器正式页面以隔离 API 验证渲染和交互，不改用户真实草稿。后端现有持久化路径另以适用测试核验，结果必须区分 Mock、浏览器与存储层。
