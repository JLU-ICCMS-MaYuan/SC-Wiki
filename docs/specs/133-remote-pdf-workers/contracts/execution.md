# 任务执行、提交与恢复契约

**来源**：[Spec](../spec.md) FR-001～FR-009、FR-012。

## 输入与执行权

API 保留现有鉴权，锁定逻辑任务的执行记录，登记输入版本与新代次；记录成功后投递 RQ。投递失败不报告“解析开始成功”，返回可重试的暂时失败并保留 pending 供恢复，重复用户请求须命中同一请求/代次而非无限创建新代次。

Worker 验证任务状态契约版本和消息身份，使用条件更新获得当前 pending 代次执行权。同代次已 running/committed/failed/cancelled 的重复消息不重新运行。输入 FileRef 取得后校验 SHA-256，不能从消息接收任意本地路径或网络 URL。

所有临时文件放 `FILE_STORAGE_TMP_DIR/<kind>/<task-id>/<attempt-id>/`；并行任务目录互不重叠。模型/解析方案按任务原选择加载，不静默换方案。凭据缺失或过期按既有规则提示用户重新选择，不从历史备份恢复秘密。

## 完成协议

1. Worker 生成本次候选结果与必需产物清单；对象键包含 attempt 身份。
2. 上传并校验全部必需文件，任何一个失败即不进入成功提交。
3. 在 MySQL 事务中锁定执行头，核验 generation、attempt_id、未过期租约、input_version 和取消状态；写入既有业务结果、manifest 与 committed 标记。
4. 事务提交后按当前代次投影 Redis 公共状态；无法投影时保留 committed，进入待同步，不重新解析。
5. 清理本次临时目录和不再需要的瞬态凭据。正式文件是否保留依据引用，不能按 Worker 退出一概删除。

所有中间持久业务写入也须校验执行头；临时向量按 attempt 隔离，不允许失效尝试覆盖已发布点。正式论文提交仍走现有用户操作和 upload_task_id 幂等规则，Worker 不越过审核直接发布论文。

中间草稿/证据候选如需落盘，使用 attempt 对象或独立候选快照；当前正式/有效记录只在最终提交事务改变。不能以“每次写入都检查租约”代替对未完成结果的可见性隔离。

MySQL 与 Redis 无跨库事务；不声称严格消息 exactly-once。执行头保障持久结果唯一有效，Redis 投影用代次比较防止版本倒退；读取默认不查询数据库兜底。新代次或取消未完成公开状态同步时，不向用户确认操作已完成。

## 故障与恢复矩阵

| 故障 | 处理 |
| --- | --- |
| 投递前/后 API 退出 | pending 代次按确定性 job id 补投；已在运行或完成的不重做 |
| Worker 重复消费 | 执行头拒绝重复获得执行权，无业务副作用 |
| Worker 退出/租约过期 | 收敛 failed，错误 `WORKER_LOST`；用户显式重新发起才新建代次 |
| MySQL 不可达 | 不提交结果；恢复后检查当前执行头再决定失败或同步，不能凭本地文件宣称成功 |
| Redis 不可达 | 不接受新任务；已运行任务可完成持久提交，公共状态在连接恢复后由投影恢复 |
| S3 下载/上传/校验失败 | 有界传输重试后 failed，保留源文件；不发布成功或不完整 manifest |
| 旧进程迟到回写 | 代次/租约/版本检查拒绝，无权修改当前业务结果 |
| 取消与成功提交竞争 | 以执行头事务顺序为准；已 committed 沿用原业务取消规则，不能删除已提交引用 |
| 清理失败 | 保留已提交业务结果与清理重试记录，不把它改成解析失败 |

稳定错误包括 `WORKER_LOST`、`EXECUTION_SUPERSEDED`、`INPUT_VERSION_CHANGED`、`ARTIFACT_PERSIST_FAILED`、`EXECUTION_TIMEOUT`，以及 #131 的存储错误。公开状态值继续沿用现有 API；详细执行身份仅在内部诊断中提供。

## 恢复入口（待实现）

```text
python -m backend.scripts.reconcile_task_executions --check
python -m backend.scripts.reconcile_task_executions --apply
```

默认只读扫描；apply 只补投当前 pending、收敛过期 running、同步 committed，不自动重跑失败任务。计算监督循环启动时及每 30 秒执行同一恢复逻辑；进程多实例通过条件更新与确定性任务 id 保证重复调用无副作用。续约每 10 秒，租约 60 秒；默认上传最大执行时间 7200 秒，核对 1800 秒，均为有限值。

日志仅包含 task_id、kind、generation、attempt_id、输入摘要、制品身份、阶段、耗时和错误码，不保存原文内容、访问密钥或内部推理。
