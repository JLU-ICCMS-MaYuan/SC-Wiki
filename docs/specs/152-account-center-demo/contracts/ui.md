# 界面与状态契约

- `?role=user|admin|superadmin&view=account`：三角色演示，默认 superadmin。
- `view=public`：隐藏邮箱、修改、密码和工作入口。
- `view=review`：管理员／超级管理员示例待检查队列。
- `view=users|applications|charts|news|models|audit`：超级管理员模块。
- 链接使用 `target=_blank`、`rel=noopener noreferrer`。浏览器 back 不承担跨标签页关闭；目标页有返回用户中心链接。
- Profile：只读 → 修改草稿 → 取消丢弃／保存后回到只读；不持久化。
- Role 仅演示开关，不提供安全保证；生产后端现有鉴权不变。
- 搜索只匹配本地标题、DOI、材料，状态筛选独立；结果为空可重置。
- 工作模块的示例申请批准、模型保存只改变本标签页状态；不模拟真实科学审核通过。
