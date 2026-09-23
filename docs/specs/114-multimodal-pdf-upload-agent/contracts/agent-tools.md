# Agent 工具契约

允许工具：`read_document`、`read_page`、`read_region`、`extract_table`、`inspect_figure`、`search_within_document`、`validate_claim`、`check_coverage`。

每个任务最多 12 次行动；单个工具最多 2 次重试。工具输入必须引用当前任务和文件身份，不能传入任意服务器路径；工具输出必须包含来源身份和可复核定位。不得提供无范围公网搜索，不保存思维链。预算耗尽、定位失败或覆盖不足时返回 `needs_review` 或 `degraded`。
