# 角色与管理员审批

## 功能说明

管理 `user`、`admin` 和 `superadmin` 三类角色、公开研究身份、管理员资格申请和可审计的账号治理。

## 当前行为

- 所有已登录角色都进入 `/account`“用户中心”；侧栏底部按角色显示“用户 / 管理员 / 超级管理员”与对应图标，旁边的头像菜单只保留退出登录。角色入口在用户中心、管理员工作台、超级管理员工作台及管理员编辑深链均标示活动状态。
- 全局顶部栏已移除；左侧主导航贴合视口顶部，展开 216px、收起 64px，高度受动态视口约束；入口超过可用高度时可在导航区域内独立纵向滚动。模型与语言位于角色入口上方，收起后仍可配置或切换；登录后语言与角色入口之间提供通知，管理员和超级管理员另有举报管理。访客底部提供登录/注册入口。
- 用户中心可维护头像、一次性用户名、真实姓名、所属机构、ORCID 和研究方向，并修改密码。除邮箱外，已填写资料通过匿名 `/users/:username` 公开；公开页设置 `noindex`。
- 资料默认只读，点击“修改资料”后编辑；姓名、机构、ORCID 在桌面同排，研究方向独立一行。取消丢弃未保存字段；保存失败保留编辑内容，成功后回到只读。
- “他帮助 SC-Wiki 收录的论文”读取本人提交，不表示作者身份；管理员与超级管理员另有本人检查记录，按不可变 `PaperHistoryEvent` 的操作者过滤，每篇取本人最近一次检查。历史结果与论文当前状态分开，其他管理员后续审核不抹去本人记录，无归属历史不推断补写。
- 检查区的“待检查”复用原有审核组件及证据流程；超级管理员工作入口提供用户权限、管理员申请、图表、快讯、默认模型和审计六个新标签页直达链接。`/superadmin?section=...` 直接展开目标模块。
- 修改密码必须先提供旧密码与本人绑定邮箱，通过服务端校验后发送随机六位验证码。验证码五分钟有效、六十秒发送冷却，复用邮箱/IP 的每小时五次、每天十次发送额度；身份验证请求另限账户/IP 每五分钟二十次。错误验证码最多尝试五次，用途、用户、邮箱、会话版本均隔离。
- 原改密接口也强制验证码；数据库行锁内复核身份和会话版本，Redis 原子消费验证码，成功后更新密码及 `session_version`，撤销当前及其他旧会话。SMTP/Redis 故障拒绝继续，数据库失败不会恢复已消费验证码。
- 头像由 Go API 先写私有文件存储、再更新用户引用；替换成功后清理旧对象，数据库更新失败时清理新对象。当前本机实例使用 Garage S3，公开资料仍通过原 API 返回头像，不暴露对象桶地址或密钥。
- 普通用户在邮箱已验证且真实姓名、所属机构齐全时可无理由提交管理员申请；同一时间只允许一个待审申请，可撤回、被拒后再次申请，申请保存资料快照。
- 超级管理员批准申请会把角色从 `user` 改为 `admin`；拒绝或管理员降级必须记录原因。申请、角色、封禁、解封、注销、实名/机构和用户名变更均保留审计。
- `/admin` 只允许 active admin；`/superadmin` 只允许 active superadmin。普通用户或管理员越权访问返回 403，superadmin 访问 `/admin` 时前端重定向 `/superadmin`。
- 超级管理员可以为任意账号带原因修改用户名；用户名更新和只追加审计事件在同一事务完成，管理员给自己更名后前端立即同步当前会话身份。
- 用户记录保存 `username`、`role`、`is_approved`、`is_email_verified`、`approved_at` 等字段；实名不是公开身份字段。

## 工作流程

普通用户注册并验证邮箱后即可使用；需要承担审核职责时从用户中心提交管理员资格申请；超级管理员在独立工作台审批。账号治理使用明确动作端点，要求原因、二次确认并在同一事务写用户状态与审计。

## 约束

- 角色值限制为 `user`、`admin`、`superadmin`。
- 图表组合、快讯、管理员申请、角色、用户状态和审计接口在后端强制 `SuperAdminRequired`，前端隐藏不作为安全边界。
- 封禁禁止登录和所有写操作，但保留公开资料与历史贡献并标注状态；注销保留用户与全部历史关系，移除公开资料和头像，历史贡献显示“已注销用户”。
- 超级管理员不能封禁、注销或降级自己；系统始终至少保留一名 active superadmin。
- 超级管理员更名必须提供 1–500 字符原因；更名不恢复或消耗历史账号的自助更名资格。

## 代码与测试

- `goserver/handlers/admin.go`
- `goserver/middleware/auth.go`
- `goserver/models/models.go`
- `backend/security.py`
- `backend/models.py`
- `frontend/src/pages/AdminPage.tsx`
- `frontend/src/pages/AccountPage.tsx`
- `frontend/src/pages/PublicUserPage.tsx`
- `frontend/src/pages/SuperAdminPage.tsx`
- `frontend/src/components/AppShell.tsx`
- `tests/02_identity_governance/identity_ui.test.tsx`
- `goserver/handlers/admin_applications.go`
- `goserver/handlers/governance.go`
- `goserver/handlers/username_test.go`

## 相关变更记录

- [Feature #152：三角色用户中心与邮箱验证改密](../../specs/152-account-center-demo/spec.md)：原型保留独立，正式页面不使用示例角色或固定验证码。

- [Feature #101：全角色统一可收起侧栏](../../specs/101-unified-collapsible-sidebar/spec.md)
- [Feature #31：唯一公开用户名与贡献榜身份](../../specs/31-community-ranking-visuals/spec.md)
- [Issue #48：修复页面滚动时左侧导航和解析收起操作不可达](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/48)

## 已知问题

- #152 已验证真实处理器、Redis 隔离集成及本地 TLS SMTP 协议；正式页面浏览器检查使用隔离接口响应。未向真实外部邮箱发送验收邮件，未声明生产部署完成。

- `is_approved` 仍为兼容字段，不再表示注册审批或管理员资格状态。
