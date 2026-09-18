# 社区接口契约

统一前缀 `/api/community`，Go 提供全部 API。读取使用 OptionalAuth，写入使用 AuthRequired 且校验 active、邮箱已验证；管理接口还要求现有管理员资格。请求体上限 128 KiB。

## 路由

| 方法与路径 | 行为 |
| --- | --- |
| GET /questions?q=&sort=latest\|active&offset=&limit= | 问题分页 |
| POST /entries | 创建 question / answer / comment |
| GET /entries/:id | 按 ID 读取并附带权限与跳转地址 |
| PATCH /entries/:id | 作者编辑 title/body |
| DELETE /entries/:id | 作者软删除 |
| GET /entries?kind=&question_id=&answer_id=&paper_id=&system_key=&sort=&offset=&limit=&focus_id= | 单一目标的答案或评论；答案默认 votes，评论按根线程及回复 ID 正序 |
| PUT /entries/:id/vote、DELETE /entries/:id/vote | 答案点赞与取消 |
| POST /entries/:id/reports | 举报，重复返回既有记录 |
| GET /systems/:key | 规范化体系、公开论文分页和目标身份 |
| GET /notifications、GET /notifications/unread | 可见通知分页和未读数 |
| PATCH /notifications/read | body.id 可选；缺省标记本人全部通知已读 |
| GET /moderation/reports | 管理员查看举报列表，附内容与最近处理记录 |
| POST /entries/:id/moderate | action=hide/restore/dismiss，reason 必填；解决该内容待处理举报 |

创建和列表的目标字段固定：answer 只带 question_id；comment 只带 answer_id/paper_id/system_key 之一，可带 reply_to_id。服务端生成 parent_id 和 author_id，忽略不了解的字段视为无效请求。question 无目标。客户端不可指定作者、状态或计数。

## 响应与失败

列表 `{items,total}`，内容包含 id、kind、title、body、status、作者公开信息、目标、parent_id/reply_to_id、votes/voted、can_edit、can_delete、can_reply、created_at/updated_at、url。评论占位清空敏感内容，保留定位 ID。

评论列表额外返回 `offset` 和 `context`：`items` 是当前页，`context` 是该页回复所需但不在当前页的根评论。指定 `focus_id` 时仅查询目标线程，未传 `offset` 时自动计算包含指定评论的页；显式传入 `offset` 后可继续翻页。答案列表的 `focus_id` 将评论或答案解析为所属答案，使通知跳转能定位跨页内容。焦点内容仍须属于当前目标且满足可见性。

400 参数或目标组合无效；401 未登录/会话失效；403 邮箱未验证、无权限、论文不可见；404 目标不存在或非公开内容；409 状态冲突；429 频率超限（附 Retry-After）；503 限流存储不可用，不能假报发布成功。统一 `{error,code}`。

## 退役类型

kind=danmaku 的创建和列表请求返回 400 invalid_community_input；历史弹幕按 ID 读取、编辑、删除、点赞、举报和管理均返回 404 content_unavailable，作为 focus_id 也不可定位。通知列表/未读数和 pending/resolved 管理举报列表均排除对应内容。记录留库，不迁移为评论。

## 通知与频率

答案通知问题作者；答案评论通知答案作者；回复通知被回复评论作者，接收者去重并排除自己。链接通过内容关系计算，读取重新检查论文及所有祖先权限；跳转到根问题或详情页并定位 `entry-<id>`。

Redis 固定窗口：同账号创建/编辑内容每分钟 30 次、问题每小时 10 次、点赞和举报每分钟 60 次；受信任代理 IP 每分钟 120 次写操作。Redis 不可用时写入失败，读取保持可用。空闲读取无永久缓存。
