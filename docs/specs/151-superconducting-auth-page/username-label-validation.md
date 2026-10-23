# 注册字段命名与用户名防重核验

## 结果

注册页中文改为“用户名”，英文改为 Username；Demo 复用共享文案。只改标签，不改变用户名公开范围、真实姓名提示、格式或大小写规则。对应 FR-022/023、SC-012、T022，归属 Issue #151。

## 三层防重

1. 前端 AuthExperience 的 checkUsername 在输入框失焦时请求 /api/auth/username-availability；重复时 available=false，显示占用提示。
2. registerHandler 在注册写入前调用 usernameAvailable；重复用户名返回 HTTP 409，不创建账号、不发送邮件。
3. users.username 有数据库唯一约束，处理预检查后并发抢占的情况；MySQL 1062 被映射为 HTTP 409。

本机 127.0.0.1:3307 只读检查：uq_users_username 的 NON_UNIQUE=0；列不可空，COLLATION=ascii_bin；完全相同用户名的重复组数为 0。没有读取或输出账号列表，没有修改数据或 schema。见 [数据库证据](assets/username-label/database-check.json)。

既有规则区分大小写：Alice 与 alice 可是两个用户名；此次不改变这项历史约定。

## 验证

- 三个前端测试文件共 37 项通过，包括新标签、失焦占用提示、直接提交收到 409 后展示错误和没有建立会话。
- Go 的 TestRegistrationRejectsDuplicateUsername、TestRegistrationMapsConcurrentUsernameConflict、TestDuplicateUsernameError 通过。隔离数据库真实唯一索引拒绝重复插入；模拟 MySQL 1062 验证并发冲突返回 409。这不是对生产 MySQL 并发压测的声明。
- TypeScript 检查通过。
- 本机正式 /auth 注册页中英文浏览器核验通过：[中文](assets/username-label/register-zh.png)、[英文](assets/username-label/register-en.png)。未使用真实邮箱发信或注册。
- 附件原图：[原图](assets/username-label/original.png)，来源及哈希见 [source.json](assets/username-label/source.json)。

本次未部署、推送、迁移或修改认证业务逻辑；现有本地实时开发页面从源码加载新标签。Issue 原有外部验收门不因本次文字调整自动完成。
