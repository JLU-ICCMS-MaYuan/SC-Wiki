# 数据模型：上传文件角色判断

| 对象 | 字段 | 含义 |
| --- | --- | --- |
| 任务文件 | `declared_role`、`role` | 用户上传前声明及当前有效角色；现有 `role` 供下游读取 |
| 任务状态 | `role_assessment` | `status=resolved|needs_review`、每文件信号与理由、`main_file_id`、来源哈希与规则版本 |
| 任务状态 | `status=needs_role_review` | 已提取文件、暂停分段 LLM，沿现有待办任务 TTL 保留 |
| 角色确认请求 | `expected_revision`、`roles[]` | 所有文件的完整角色表，恰好一份 main；仅待确认任务的所有者可提交 |

文件 bytes、SHA-256 与 file_id 不变。角色改变时任务 revision 增加；来源版本纳入字段核对哈希。状态与草稿通过 Redis 和已有 `ScientificUploadDraft` 持久化，不新增数据库列。旧任务缺 `declared_role` 时以原 `role` 作为历史声明，只对待重算的未提交草稿执行有界修复。
