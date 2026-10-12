# 执行身份与结果模型

**Issue**：[ #133](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/133)。拟新增模型，不是当前数据库事实。

## task_execution_heads

每个逻辑任务一行，组合主键为 `task_kind`（upload/evidence/shadow）和 `task_id`。三种任务共用执行协议，但原有各自业务状态保持兼容。

| 字段 | 约束 |
| --- | --- |
| `generation` | 正整数，创建为 1，显式重试/作废时单调递增 |
| `attempt_id` | 当前执行 UUID，不可复用到另一代次 |
| `input_version` | 输入 manifest、草稿/论文 revision 与模型选择标识的规范摘要；不含密钥 |
| `owner_user_id` | 原任务用户归属；不替代各业务入口鉴权 |
| `state` | pending、running、committed、failed、cancelled |
| `dispatch_pending` | 记录当前代次是否需要补投；只有 pending 可补投 |
| `worker_id`、`lease_until` | 当前持有者和数据库时间租约；仅 running 使用 |
| `artifact_manifest` | 完成产物的 FileRef 数组、必需标记、用途与输入关联 |
| `result_snapshot` | 可重建 Redis 公开结果所需的有限业务快照/持久引用；不保存凭据 |
| `error_code` | 稳定脱敏错误码 |
| `created_at`、`updated_at`、`committed_at` | UTC 时间 |

新增 Alembic 迁移只增加此表及必要索引，不自动重写业务 schema。上传/证据核心结果继续保存现有科学草稿、证据、论文等表。本记录的提交标记和同次业务结果必须共用数据库事务。

`result_snapshot` 只允许公开 DTO 重建所需的字段与持久引用白名单，禁止直接复制含临时模型配置的内部 state。未提交的中间科学结果按本次 attempt 隔离，或仅在最终提交事务写入；不得在提交前修改当前正式论文或让未提交证据成为当前有效结果。

## 执行转换

新请求：pending → running → committed，或 running → failed/cancelled。pending 投递失败保留 pending 与 dispatch_pending。committed 不再执行解析，只允许重建状态投影；显式重新解析先校验原有业务规则并生成下一 generation。

取消在同一事务中作废当前执行权；输入版本改变也使旧执行提交失效。旧进程只能清理属于自身且未被引用的对象。历史 attempt 的审计信息保存在不可变运行元数据与日志中，本表只保存当前头，不新增无限增长的全量任务副本。

## Redis 和队列

队列保持 `scwiki-upload`，消息传递 task_id、task_kind、generation、attempt_id、input_version；文件内容在对象存储，模型凭据仍在既有短期键。RQ job id 为 `<kind>:<task-id>:<generation>`。

Redis 公共状态保留原字段和状态值，内部增加执行版本与提交指针；状态契约版本升级一次，API 和 Worker 必须匹配。列表继续读 Redis；MySQL 是执行权和已持久提交的证明。投影允许短暂滞后，不能从旧代次覆盖新代次；用户成功取消/重新发起响应前须完成对应 Redis 版本推进或返回可重试未完成状态。

## 产物分类

必需产物：主文/附件生成的 Markdown、该解析方案要求的 IR/Claim/覆盖报告、审核快照及当前结果读取必需的文件。格式和科学内容沿用 #114，不新增另一套 IR。实际必需集合由所选 pipeline 的声明生成，不能硬编码“所有方案都有同样文件”。

运行耗时日志、即时证据截图、模型缓存、下载缓存不是成功提交的必要业务产物；运行身份的最小摘要必须写入提交 manifest，额外诊断日志失败不覆盖已提交业务结果。

清理规则继承 #131 与 #35；不能仅按 bucket 前缀/年龄删除所有对象。以 attempt 归属、当前执行头和正式/返修引用检查决定是否可删除。
