# 认证同步调查与设计取舍

关联：[规格](spec.md)、[Issue #171](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/171)。

## 已核实事实

- AuthContext 用 auth_token/auth_user 存储认证信息；只在挂载时恢复，无 storage/focus/visibilitychange 监听。
- /api/auth/me 的旧响应可调用 saveAuth 写回旧 token；任何失败都会 clearAuth，包括网络错误。
- 通用 API 客户端每次读取 getStoredToken，UploadPage 也直接读取 auth_token；保留该凭据键，避免扩散接口改动。
- AuthPage 仅在本页提交成功回调中跳转；外部登录需要额外响应用户状态。
- replaceUser 与 updateUsername 可能持有旧凭据或旧用户闭包。

## 决策

1. 复用浏览器原生 storage 事件，以 focus/visibilitychange 补漏。不增加 BroadcastChannel、轮询、后端会话服务。
2. 保留 auth_token/auth_user；增加 auth_session_revision 作为登录/退出世代标记。即便服务端短时间签发相同 JWT，旧响应也无法越过新世代。旧存储没有标记时使用空世代，首次登录/退出自动写入，不批量迁移。
3. 跨标签页的新凭据必须经现有 /api/auth/me 获取匹配的用户身份，不盲目信任两个存储键的短暂组合；客户端权限不替代服务端校验。
4. 只向缓存回写 user，不由 /me 响应重新写 token。异步响应同时校验当前存储凭据、世代及本页请求代次；卸载后丢弃。
5. 401/403 才撤销当前匹配会话；网络异常、5xx 和响应解析异常保留共享凭据，允许恢复焦点重试。新身份尚未核验时不显示旧用户。
6. 相同会话合并核验，重复相同缓存写入不发送循环事件。监听清理与取消响应明确归属 Provider。
7. AuthPage 仅对非本页正在完成的认证自动回跳，保留注册验证默认 /account 与普通登录默认 /news 的区别。
8. replaceUser 及更名返回仅可更新仍属于该会话的同一用户，不能让旧账号信息污染新会话。

## 备选方案

- 强制刷新全部标签页会破坏页面与编辑状态，拒绝。
- 只加 storage 监听无法处理后台遗漏及迟到响应，拒绝。
- 改 Cookie、合并全新存储格式或引入全局状态库超出当前必要范围，拒绝。

## 验证边界

组件测试控制响应顺序；真实浏览器共享上下文验证原生 storage 分发。复用隔离 Go 认证夹具（SQLite、miniredis、邮件捕获）验证实际认证 HTTP 路径，不触及生产账号；非认证业务响应可隔离。此验证不证明线上部署已修复。
