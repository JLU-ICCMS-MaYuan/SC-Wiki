# 数据模型

community_model_answers：问题、config_hash、首答 entry_id、first_sequence；问题+身份唯一，条目唯一。
community_answer_requests：UUID唯一、问题、递增序号、发起人、模型安全元数据/配置指纹、状态、RQ ID、时间、上下文快照、来源、成功条目/追加ID、retry_of；问题+序号唯一。
community_answer_turns：所属首答条目、请求ID唯一、正文/引用/回应、版本与人工修订标记、时间。
community_answer_turn_revisions：追加段、版本、旧正文和引用、操作者与时间，段+版本唯一。

无凭据存数据库。首答不复制到追加表；Go 组装统一 turns 返回。隐藏整卡隐藏全部追加；上下文依赖沿输入可见性动态校验。
