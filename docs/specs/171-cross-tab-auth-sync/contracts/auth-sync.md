# 认证同步与导航契约

## 事件

监听同源 localStorage 的 auth_token/auth_user/auth_session_revision 与 clear 事件；忽略其他键、sessionStorage。
短时间多键事件合并读取当前值。focus 与可见状态的 visibilitychange 执行同一同步入口。
Provider 卸载移除监听并使在途请求失效。

## 身份核验

GET /api/auth/me 与现有 Bearer JWT 契约不变。新凭据核验完成才采用匹配用户。
401/403 撤销仍匹配的会话；网络异常与 5xx 不清共享会话。相同会话核验去重，无轮询。

## 写入

login、verifyEmail 在成功时建立新世代；logout 清认证并更换世代。旧请求检查凭据与世代，失配则丢弃，不再次写存储。资料更新须校验会话和用户 ID。

## 页面行为

普通业务页不主动刷新或导航；已有权限组件响应 user 变化。
/auth 收到外部有效用户后使用 safeAuthReturnTo；没有安全来源则 /news。
本页注册验证的既有成功回调仍可前往 /account，无跳转竞争。
