# 数据模型

community_entries 增加来源（human/ai）、分类、模型 ID/名称/型号、目录顺序、引用 JSON、人工修订标记、版本及问题标题指纹；author_id 可空，AI 使用空作者。问题指纹仅新生成问题使用，历史不回填。AI 答案由任务唯一关联，不改变历史真人答案。

community_ai_batches 保存请求 UUID、发起人、请求参数摘要、问题、来源快照、状态、错误码及创建时间。community_ai_tasks 保存批次、模型安全元数据与配置身份指纹、答案 ID、状态、RQ 任务 ID、尝试次数、开始/结束时间及问题/答案基线版本；批次与模型唯一。

community_entry_revisions 保存修改前的正文、引用、人工修订标记、版本、操作者与时间；条目与版本唯一。凭据只进入限时 Redis 键，不进入公开 DTO、修订或日志。

状态为 queued/running/succeeded/failed；批次另允许 partial。失败码为受控枚举，不透传上游错误。MySQL 事务的祖先锁及版本比较在 Go/Python 两侧一致。
