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

## 本轮token消耗

新增可选extraction_token_usage：

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| run_id | 字符串 | 本轮随机身份；新任务及显式失败重试重建 |
| input_tokens | 非负整数 | 有效回执实际输入累计 |
| output_tokens | 非负整数 | 有效回执实际输出累计 |
| total_tokens | 非负整数 | 实际总量累计，等于输入与输出之和 |
| request_count | 非负整数 | 已开始的物理模型请求数，包含失败和未结束请求 |
| recorded_requests | 非负整数 | 已收到完整有效用量并计入的请求数 |

私有_extraction_token_requests以request_id记录pending/recorded/missing，用于去重；不进入公开DTO。内部_token_usage_event仅作为状态转换指令消费，不持久保存为状态字段。

新任务及retry=True同时初始化轮次与私有请求表；暂停/继续及普通保存均保留。同一run_id的请求结束最多计量一次。旧run_id、未登记请求和旧执行代次不得增加新轮统计。统计缺失的历史任务不补造对象。

request_count大于recorded_requests时存在未结束/未知用量；有已知量则展示已记录值并标注不完整，全部未知显示未记录。request_count=0且确知本轮初始化后未发出请求时为真实0；尚未开始沿用未开始提示。记录与私有去重表随既有任务快照保存和恢复。
