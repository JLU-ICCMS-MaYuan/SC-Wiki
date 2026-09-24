# Agent 工具契约

允许工具：`read_document`、`read_page`、`read_region`、`extract_table`、`inspect_figure`、`search_within_document`、`validate_claim`、`check_coverage`。

每个任务最多 12 次行动；单个工具最多 2 次重试。工具输入必须引用当前任务和文件身份，不能传入任意服务器路径；工具输出必须包含来源身份和可复核定位。不得提供无范围公网搜索，不保存思维链。预算耗尽、定位失败或覆盖不足时返回 `needs_review` 或 `degraded`。


当前有限修复循环最多 12 轮工具选择；失败与重试计入行动预算，每工具重试最多 2 次。
修复只能给已有、同值、同路径的科学候选补充经验证的出处，不能把模型新值自动写回。
日志保存工具名、文件、页/块/表标识和结果摘要，不保存自由思考文字。inspect_figure
当前返回 IR 中的图像区域资料，尚不等于视觉供应商读图验收。
