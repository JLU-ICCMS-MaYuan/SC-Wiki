# 演示实施计划

## 正式接入计划（当前阶段）

- AccountPage 复用 React/MUI 及原侧栏，拆分 AccountSecurity、AccountWorkEntries、AccountReviews，MyPapersList 共用收录／本人检查列表。只迁入已确认账户区域视觉，不重做全站导航。
- 新增 `POST /api/account/password-change-code` 接收 current_password/email；原 change-password 新增 email/code 必填。复用 TLS SMTP、Redis 限流及原子消费，摘要绑定改密用途、用户和会话版本。数据库行锁内再次核验状态与版本，成功事务更新密码和 session_version；数据库失败不恢复已消费码。
- 新增 `/api/account/reviewed-papers`，按 PaperHistoryEvent 的本人 reviewed 事件去重，每论文取最近一次本人操作；不迁移 schema。
- AdminPage 支持嵌入审核及 section 深链，SuperAdminGovernance 支持目标分区；复用现有真实审核和管理组件。
- 映射：FR-007/008、SC-006 → T009；FR-003/005 → T010；FR-001/002/004、SC-007 → T011；T012 为综合验证和事实文档回写。下文原型计划为历史记录。

**Issue**：[ #152](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/152) · **日期**：2026-10-22 · [Spec](spec.md)

## 技术上下文

独立目录 `prototypes/account-center`，Product Design prototype 模板；React 19、Vite 6、MUI 7 图标。数据仅 React 状态，不使用生产 API、认证或持久化。保留模板托管运行文件，但本轮不部署。

## 组件职责与结构

`src/App.jsx` 中 Profile 负责查看／草稿编辑；PaperList 复用收录和检查结构；WorkEntries 管理六入口；Workspace 演示直达；Security 折叠密码区；Sidebar 沿用导航视觉。`src/styles.css` 只影响独立 demo。URL 使用 role/view 区分角色与模块，不影响生产路由。

## 质量门

| 来源 | 约束 | 满足方式 |
|---|---|---|
| AGENTS.md | 保留并行工作、限定提交 | 只新增原型及 152 文档，不改其他待提交内容 |
| 用户 | 先做 demo | 不接生产数据；正式实施待评审 |
| Product Design | 视觉及交互验证 | 用户授权 Playwright；桌面／小屏截图和原图比较 |
| Spec | 公开邮箱隐藏 | public 视图不渲染邮箱、编辑与管理入口 |

## 需求映射

| 需求／验收 | 组件与事实来源 | 任务／证据 |
|---|---|---|
| FR-001/002、SC-001/002、US1 | Profile；原图 1 和用户要求 | T002；浏览器编辑与布局检查 |
| FR-003/005、SC-003、US2 | PaperList；原图 2/3 | T003；角色、筛选、详情检查 |
| FR-004、SC-003、US3 | WorkEntries/Workspace；现有工作台卡片 | T004；新标签页目标检查 |
| FR-006、SC-004 | App 隔离入口和 public 条件展示 | T005；网络与公开页检查 |

## 执行顺序

T001 需求留档 → T002 资料 → T003 贡献 → T004 工作入口 → T005 QA／构建。简单共享组件避免三套页面重复；没有新后端或抽象框架。

## US4：邮箱验证码改密

FR-007/008、SC-005 → Security 独立两步状态 → T007。第一步校验示例身份；第二步模拟绑定邮箱验证、新密码及确认输入；用时间戳计算倒计时和有效期，成功后只更新当前角色的演示密码。状态留在组件内，角色变化重新挂载，取消销毁挑战。不添加 API、数据库或真实邮件。
