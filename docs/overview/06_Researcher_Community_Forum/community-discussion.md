# 社区问答、评论与弹幕

## 功能说明

研究者可以独立提问、回答，在答案、体系和论文下评论或回复，并在体系和论文的独立区域发送弹幕。所有业务接口由 Go 提供；Python 仅登记数据库元数据。

## 当前行为

- 侧栏社区展开 `/share/rankings`、`/share/charts`、`/share/discussions`。旧 `/share` 重定向至图表。问题列表支持关键词、最新和最近活跃排序；答案默认按赞同数排序，也可按最新排序，不设采纳。
- 问题与答案支持 Markdown、链接、代码、公式和预览，不执行原始 HTML，也不渲染图片。评论、回复、弹幕为纯文本。
- 元素搜索提供 `/systems/:systemKey` 入口，例如 Hg。元素符号区分大小写，组合去重后按字母顺序生成稳定标识；不同论文共用同一体系讨论，页面仅列出该体系当前公开论文。
- 独立论文详情、搜索论文详情和图表论文抽屉共用 `PaperCommunity`。论文评论按论文 ID 关联，修改版本不丢失评论；体系评论与论文评论互不混合。
- 评论按根评论归组，回复在根评论下平铺并标明回复对象。分页补上根评论上下文，通知跳转能定位到长线程中目标回复所在页。
- 正常且邮箱验证通过的账号可直接发布，游客可阅读公开内容。作者可编辑问题、答案、评论并删除自己的内容；弹幕只能删除。评论隐藏或删除后留下无正文占位及已有回复，不能继续回复该评论；问题或答案不可见时，后代也不可访问。
- 弹幕每 3 秒读取最新 50 条快照，同一播放会话按 ID 去重，最多六条同时播放，其余排队。隐藏内容在下一次成功刷新时移除。关闭或离开目标停止轮询，页面在后台时跳过请求；历史独立分页。减少动画偏好使用静态展示。临时网络失败不重播已播放消息。
- 新答案、答案评论和评论回复生成站内通知，排除操作者自己。`/account/notifications` 提供未读数、列表、单条和全部已读以及内容定位；不发送邮件、浏览器推送或点赞通知。
- 用户可举报。管理员在 `/admin/community` 查看举报，填写理由隐藏、恢复内容或驳回举报；保留处理事件。作者不能恢复管理员隐藏的内容。

## 数据与权限

`community_systems` 保存独立体系空间；`community_entries` 保存有明确目标外键的四类内容；点赞、举报、处理事件、通知分别保存。论文物理删除时级联清理对应互动，体系讨论保留。

论文互动复用论文可见性规则，通知读取时重新检查内容和祖先权限，不保存正文快照。写入在事务中按祖先到后代锁定并读取当前权限，避免隐藏与回复并发时继续向失效目标发布。点赞使用唯一约束保持幂等。

请求体上限 128 KiB；标题 3–200 字，问题及答案正文最多 20000 字，评论 2000 字，弹幕 120 字。账号与 IP 通过 Redis 限流，Redis 不可用时拒绝写入。对外只展示用户名、头像和账号状态标记，不返回邮箱；注销账号匿名显示。

## 约束

- 当前实现不包含图片附件、私信、关注、推荐或实时长连接。
- 弹幕是有界快照展示，密集消息可能超过轮询窗口；完整历史通过分页回看。
- 代码包含迁移 `20260917_0107`，依赖 `20260916_0106`。隔离环境验证与现有部署分开记录，本文不表示现有数据库已迁移或服务已更新。

## 代码与验证

- 服务：`goserver/handlers/community*.go`、`goserver/models/community.go`。
- 前端：`frontend/src/components/community/`、`frontend/src/pages/DiscussionPage.tsx`、`SystemCommunityPage.tsx`、`CommunityNotificationsPage.tsx`、`CommunityModerationPage.tsx`。
- 元数据及迁移：`backend/community/models.py`、`alembic/versions/20260917_0107_community_discussion.py`。
- 验证：`goserver/handlers/community_test.go`、`community_mysql_test.go`、`tests/07_researcher_community_forum/community-discussion.test.tsx`、`verify-community.py`、`community-browser.mjs`。
- [Feature #106 规格](../../specs/106-community-discussion/spec.md)与[验收记录](../../specs/106-community-discussion/quickstart.md)。
