# 实施计划：社区问答、评论与弹幕

**Issue**：[ #106](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/106) · **Spec**：[spec.md](spec.md)

## 技术上下文

React 19、TypeScript、MUI 7、React Router 6；Go、Gin、GORM；MySQL 8、Redis；Alembic 管理结构。复用 react-markdown、remark-gfm、remark-math、rehype-katex，不新增编辑器和推送依赖。

## 设计与职责

- `goserver/models/community.go` 定义社区实体；`goserver/handlers/community*.go` 实现内容、权限、通知及管理。权限校验集中，论文目标复用 canViewPaper，写入复用当前账号校验。生产社区路由全部由 Go 提供。
- `backend/community/models.py` 只登记 SQLAlchemy 元数据，导入 Alembic 与初始化入口，不实现另一份业务 API。迁移追加到工作区现有 20260916_0106，不改写原链和并行分支。
- 内容使用带类型和明确外键的统一表，避免四套作者、软删除和治理逻辑；体系空间使用 system_key 主键。通知在内容事务内创建，点赞唯一约束保证幂等。
- 前端新增 `frontend/src/components/community/` 和 `frontend/src/pages/DiscussionPage.tsx`、`SystemCommunityPage.tsx`；公共客户端只传明确目标。评论组件负责分页、回复、编辑和登录入口；弹幕独立轮询，按目标销毁状态。
- 社区路径 `/share/rankings`、`/share/charts`、`/share/discussions`，问题详情 `/share/discussions/:id`，体系 `/systems/:systemKey`，通知 `/account/notifications`，管理 `/admin/community`。旧 `/share` 重定向到图表，保留旧书签语义。
- 三个论文详情入口挂载同一 PaperCommunity 组件，直接复用已加载论文数据提取可用体系标识；元素搜索结果增加显式体系讨论入口，不改变原检索语义。
- 不缓存权限敏感内容和通知；弹幕每 3 秒获取最新 50 条可见内容快照，ID 去重播放并移除隐藏项，历史独立分页。默认动画开启，减少动画偏好时静态展示；关闭动画停止自动轮询但仍可手动看历史。
- 评论按根线程归组分页，返回缺失根上下文，通知焦点自动定位页；同目标刷新保留未提交草稿。写事务按祖先到后代锁定并重查当前权限，避免隐藏与回复并发时写入失效目标。

## 质量门与映射

| 来源 | 设计与任务 | 验证 |
| --- | --- | --- |
| FR-001、FR-012 | 导航和独立页面，T004、T008 | 导航、窄屏、原榜单双图回归 |
| FR-002、FR-007、FR-008 | 内容服务和编辑器，T003、T004 | 问答、排序、编辑、恶意内容 |
| FR-003、FR-004、FR-006 | 目标权限和共用评论，T002、T005 | 三入口、版本与可见性、跨目标 |
| FR-005 | 独立弹幕，T006 | 双浏览器、去重、停启和隐藏 |
| FR-009、FR-010 | 通知与治理，T007 | 事务通知、已读及举报处理 |
| FR-011 | 唯一约束、限流、身份映射，T002、T003、T007 | 并发点赞、封禁、注销、超限 |
| SC-001–SC-005 | T009、T010 | 集成和浏览器记录 |

文档门：无未决高影响决策；产物齐全；需求均映射到任务和验收。实现门：真实生产路径、行为测试和隔离集成验证，不用源码文本断言代替行为。关闭门：Overview、README 与验收完成。

## 实施顺序与边界

文档 → 数据与权限 → 问答 → 详情评论 → 弹幕 → 通知管理 → 集成与文档。共享文件串行修改。工作区已有其他修改，记录起始快照并只暂存本次差异。不创建或切换分支，不推送。现有数据库迁移需在脚本和验证结果可审查后单独确认。
