# 数据模型

上传任务新增可选 `extraction_timing` 对象（Redis任务状态及已有状态快照），不新增数据库表或迁移。

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| elapsed_seconds | 非负整数 | 已结算的解析区间秒数 |
| started_at | 整数秒或null | 本轮首次进入正文提取的服务端Unix时间 |
| running_since | 整数秒或null | 当前未结算区间起点，暂停/终止为空 |
| finished_at | 整数秒或null | ready/failed/cancelled/duplicate终止时间 |

新任务初始化0及三个null。queued→extracting设置首次起点和当前区间；正文提取、分段、汇总间转换保持区间；needs_role_review、queued暂停并累计；ready/failed/cancelled/duplicate结算并固定。cancelling到cancelled前仍为运行时间。submitted及用户访问/编辑不改变已固定计时。
失败重试（retry=True）初始化新一轮，实际运行前不开始。旧任务没有对象则继续缺失，明确重试后获得新对象。无效数据不展示精确时长；秒差取非负以防短时系统时钟回拨。计时对象由后端状态转换独占写入。
