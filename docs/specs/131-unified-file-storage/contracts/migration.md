# 历史文件迁移契约

**来源**：[Spec](../spec.md) FR-007、FR-008、FR-010。以下命令为待实现接口，当前不能执行迁移。

```text
python -m backend.scripts.migrate_file_storage scan --source-root PATH --manifest PATH
python -m backend.scripts.migrate_file_storage copy --manifest PATH
python -m backend.scripts.migrate_file_storage verify --manifest PATH
python -m backend.scripts.migrate_file_storage switch --manifest PATH --apply
python -m backend.scripts.migrate_file_storage rollback --manifest PATH --apply
```

`scan` 只读；`copy` 只写目标对象和迁移日志；`verify` 完整回读内容校验；`switch` 与 `rollback` 无 `--apply` 时只输出变更计划。输入路径支持空格。出口码 0 成功、2 前置/契约错误、3 外部存储错误、4 完整性/引用冲突；日志逐项脱敏。

## 迁移步骤

1. 关闭上传和其他写入入口，停止资讯调度；排空上传、核对、资讯执行任务，停止 Worker 和写入 API。保留管理命令对数据库与对象存储的连接。
2. 备份 MySQL、必要 Redis 业务状态和源文件，记录应用版本、schema、源数据根及 manifest 身份。扫描登记引用，包括待审核快照、人工证据、返修和头像。
3. 未知引用、丢失文件、符号链接或源根越界均阻断。根据原引用映射分配稳定目标键，多引用同一文件共享同一映射。
4. 复制并回读验证。目标已有同键同内容可跳过，不同内容阻断；源在扫描后变化必须重新扫描。不能把 ETag 当 SHA-256。
5. 全部核验通过后，停写状态下条件更新 MySQL/Redis 的已登记字段；逐项记录旧值与完成阶段，保留原 TTL 的剩余时长，不重新延长草稿寿命。
6. 更新未完成或重跑遇到内容漂移时保持维护状态；不删除对象或源文件，不开放半迁移应用。
7. 使用 S3 配置启动同版本服务并执行冒烟测试，开放写入前完成零悬空引用核验。

## 凭据和队列

不导出 Redis 会话、邮箱验证码、RQ 执行队列或 `upload:llm:*` 临时模型密钥。待处理任务须先处理为已排空或明确待用户重新发起；不自动复活旧执行任务。存续草稿可恢复，凭据缺失时提示重新选择模型。生产切换不可通过恢复全量 Redis 快照来重放旧任务。

延迟清理的业务目标、原到期时间和确定性标识必须保存到迁移清单；恢复后从这些元数据重建清理计划，不恢复原始 RQ 作业或延长保留期。同实例文件切换不重建已有计划，只有 Redis 恢复/迁移时按幂等规则重建。

## 回退边界

尚未开放目标新写入时，依据旧值记录恢复引用、旧应用配置和源文件读取。恢复过程也须逐项校验并支持续跑。开放新写入后禁止直接回退旧快照，应继续前向修复或另制定增量回迁；本命令拒绝把这类回退当作安全自动操作。

所有阶段都保留源文件；源清理属于后续独立授权操作。迁移包不得成为新的项目行动状态来源，Issue 仍是唯一协作状态来源。
