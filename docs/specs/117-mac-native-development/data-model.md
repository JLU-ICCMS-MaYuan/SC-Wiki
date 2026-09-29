# 数据与状态

- 原生实例：.local/deployment-environment.json 保存独立 Conda 前缀与制品版本；.local/deployment-state.json 记录操作归属和完成阶段。
- 业务数据：.data/ 保存数据库本地文件与附件；.env 保存本机凭据，不入库、不进入冻结包。
- 进程：.local/run/<服务>.pid 指向独立进程组；操作前验证工作目录或命令、会话与监听者，不接管外部服务。
- 数据包：沿用 .deployment 清单及摘要；只接受匹配源码/服务约束的包，不复用 Linux 数据库物理目录。
- 迁移备份：.local/backups/ 下保留从旧实例导出的逻辑数据及核对报告。生命周期为导出→校验→原生恢复→核对→清理旧环境；失败停在当前阶段，备份不删除。
