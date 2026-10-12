# 使用与验收：远程解析计算

**Issue**：[ #133](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/133)。本轮未实现或运行新增模块；以下为将来必须执行的验收路径。

## 前置条件

#131/#132 已通过所需验收；准备固定 release、隔离业务数据和三台同云私网 Linux 主机。PDF 样本含正文、补充材料、结构附件、人工证据、返修及已发布论文；外部模型按原方案配置，不因部署测试改变抽取算法。

## 自动化入口（待实现）

```bash
python -m pytest "tests/01_decentralized_uploading/test_task_execution_heads.py" "tests/01_decentralized_uploading/test_remote_pdf_workflow.py" "tests/01_decentralized_uploading/test_remote_worker_failures.py"
python -m backend.scripts.reconcile_task_executions --check
```

MySQL/Redis/S3 都应是真实隔离服务。必须包含终止真实 Worker 子进程与断开连接的测试；Mock 只用于局部逻辑。reconcile 默认只读，apply 只在明确隔离实例运行。

## 拓扑矩阵

| 场景 | 位置 | 必需证据 |
| --- | --- | --- |
| 单机 | A：app/data/compute | 同一 release 三项目，完整任务和业务回归 |
| 两机 | A：app/compute；B：data | #132 数据迁移结果，跨私网 API/Worker 连接及文件读写 |
| 三机 | A：app；B：data；C：compute | C 无 A 的目录或凭据，仍完成全链路；GROBID 使用 C 私网端点 |

每种拓扑验证登录、检索、RAG、资讯、头像、授权附件读取；上传主文/附件 → 解析 → 校对 → 证据核对 → 提交 → 审核。验证审核和证据权限没有被存储键绕过。外部 LLM/SMTP 未配置则保留对应验收未完成，不用假模型结果宣称真实业务通过。

## 故障矩阵

| 注入点 | 预期 |
| --- | --- |
| RQ 重复投递同一代次 | 只有一个有效执行，不增加正式记录 |
| Worker 解析中被终止 | 租约过期被收敛为 failed；用户显式重新发起才执行新代次 |
| 上传一个必需产物失败 | 不发布成功，不生成不完整提交指针 |
| 对象全上传、MySQL 提交前退出 | 对象未引用，任务不成功；清理不影响其他尝试 |
| MySQL 提交后、Redis 投影前断连 | committed 可核验；恢复只同步状态，不再调用模型 |
| 旧进程在取消/重试后回写 | 拒绝旧代次，当前结果/证据不变化 |
| 原输入被改动或哈希不符 | 明确失败，不处理来源不一致的文件 |
| 删除节点缓存并重启 | 已提交附件/产物/审核读取不受影响 |
| 清理执行中退出 | 重跑幂等，不误删正式论文/返修/当前代次对象 |
| 模型配置过期 | 保持原有明确错误，不能回退其他模型偷偷重跑 |

## 迁移与记录

按 [计算迁移契约](contracts/compute-migration.md) 从两机扩为三机，演练开放任务前回退和迁移后排空再回退；B 不恢复旧数据快照。记录 release、主机角色、执行身份、持久提交证明、对象摘要、任务数量和故障日志。

完成后写 `validation.md`；单机容器隔离、真实两机、真实三机分别列状态。真实机器尚未提供时，保留 SC-005 未验收，不能用静态配置检查替代。
