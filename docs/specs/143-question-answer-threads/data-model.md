# 数据模型

community_model_answers：问题、config_hash、首答 entry_id、first_sequence；问题+身份唯一，条目唯一。
community_answer_requests：UUID唯一、问题、递增序号、发起人、模型安全元数据/配置指纹、状态、RQ ID、时间、上下文快照、来源、成功条目/追加ID、retry_of；问题+序号唯一。
community_answer_turns：所属首答条目、请求ID唯一、正文/引用/回应、版本与人工修订标记、时间。
community_answer_turn_revisions：追加段、版本、旧正文和引用、操作者与时间，段+版本唯一。

无凭据存数据库。首答不复制到追加表；Go 组装统一 turns 返回。隐藏整卡隐藏全部追加；上下文依赖沿输入可见性动态校验。

community_answer_groups：request_id主键(UUID)、question_id外键、actor_id外键、model_keys有序JSON、item_ids子请求UUID列表、created_at。组及全部子请求一事务创建。旧单模型request_id若无group按原契约识别，不改变既有行；新子请求UUID由组UUID和位置派生。
