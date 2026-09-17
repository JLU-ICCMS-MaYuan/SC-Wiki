# 实施任务：社区问答、评论与弹幕

输入：[规格](spec.md)、[计划](plan.md)、[决策](research.md)、[模型](data-model.md)、[契约](contracts/api.md)。

## 阶段 1：准备

- [x] T001 创建 Issue #106 与 docs/specs/106-community-discussion/ 完整设计，完成需求检查和映射。

## 阶段 2：基础能力

- [x] T002 建立 goserver/models/community.go、backend/community/models.py、alembic/versions/20260917_0107_community_discussion.py 及目标权限和持久化测试。

## 阶段 3：US1 问答（P1，最小闭环）

- [x] T003 [US1] 在 goserver/handlers/community_test.go 覆盖权限、问答、点赞、排序和安全边界，并实现 goserver/handlers/community*.go 与 main.go 路由。
- [x] T004 [US1] 在 frontend/src/pages/DiscussionPage.tsx 与 components/community/ 建立列表、详情、编辑器和安全渲染，并补充 tests/07_researcher_community_forum/community-discussion.test.tsx。

独立验收：双账号问答与答案评论、点赞排序。

## 阶段 4：US2 详情评论（P1）

- [x] T005 [US2] 在 frontend/src/pages/SystemCommunityPage.tsx、pages/SearchPage.tsx、pages/share.tsx、pages/PaperDetailPage.tsx 接入稳定体系和共用 PaperCommunity 评论。

独立验收：Hg 体系与不同论文隔离，三个入口一致；版本修改及论文权限变化不泄漏。

## 阶段 5：US3 弹幕（P2）

- [x] T006 [US3] 在 frontend/src/components/community/DanmakuPanel.tsx 实现快照轮询、动画开关、历史和清理，并测试目标切换和隐藏。

独立验收：双浏览器同步与暂停、历史、错误重试。

## 阶段 6：US4 通知与治理（P1）

- [x] T007 [US4] 实现 goserver/handlers/community_notifications.go、community_moderation.go 与 frontend/src/pages/CommunityNotificationsPage.tsx、CommunityModerationPage.tsx，验证通知权限和审计。

独立验收：通知生成、已读、定位，举报隐藏与恢复。

## 阶段 7：集成与收敛

- [x] T008 接入 frontend/src/components/AppShell.tsx、LazyRoutes.tsx 与 i18n 双语字典，拆分排行榜和 Tc 双图导航并验证窄屏。
- [x] T009 执行 Go、真实隔离 MySQL/Redis、Vitest、前端构建与浏览器验证，记录 docs/specs/106-community-discussion/quickstart.md。
- [x] T010 使用 Overview Skill 更新 docs/overview/06_Researcher_Community_Forum/、检索及迁移说明和 README.md，核对任务差异并自动提交，按验收状态更新 Issue。

## 依赖与需求覆盖

T001 → T002 → T003 → T004 → T005 → T006 → T007 → T008 → T009 → T010。共享文件串行；新增模块可独立验证。本次完整交付四个用户故事，最小闭环不是最终停止条件。

| 需求 | 任务 |
| --- | --- |
| FR-001、FR-012 | T004、T008、T009 |
| FR-002、FR-007、FR-008 | T002、T003、T004 |
| FR-003、FR-004、FR-006 | T002、T003、T005 |
| FR-005 | T006、T009 |
| FR-009、FR-010 | T007、T009 |
| FR-011 | T002、T003、T007 |
| SC-001–SC-005 | T009、T010 |

## 收敛验证

- 长线程通知自动定位、根评论上下文与回复归组：Go 行为测试。
- 弹幕六槽排队、隐藏待播内容、网络恢复不重播：Vitest 行为测试。
- 点赞保留答案及评论草稿：真实浏览器。
- 隐藏根评论与回复、隐藏答案与评论并发：真实 MySQL 屏障测试，修复体系无条件 upsert 和管理事务锁顺序。
- 上述完成指代码与隔离验收；现有环境迁移、部署及后续验收由 Issue #106 跟踪，尚未执行。
