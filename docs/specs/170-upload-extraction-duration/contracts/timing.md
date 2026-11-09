# 上传计时接口与显示契约

现有 `GET /api/upload-tasks` 和单任务读取公开可选 `extraction_timing`，字段见[数据模型](../data-model.md)。保持现有所有者权限、响应包装、错误码；无新接口。

前端每秒显示累计值加当前运行区间差，文本为“提取内容用时：{minutes} 分 {seconds} 秒”，英文为“Extraction time: {minutes}m {seconds}s”。尚未开始的新任务显示“尚未开始”，旧任务或无效字段显示“未记录”。暂停和终态仅显示已结算秒数。

存在uploading/queued/extracting/reading/summarizing/cancelling/needs_role_review任务时每3秒刷新列表，避免在旧状态上一直计时。失败显示现有错误消息；恢复读取后校正。前台定时器会受浏览器节流，页面再次获焦立即重新读取，不承诺后台标签每秒绘制。刷新不写入任务。

标题旁增加独立文本，宽屏同排、窄屏换行，保留整条打开新标签及复选框、取消、清理的点击边界。多个文件仍显示任务总用时。

## token公开字段与显示

原列表和单任务GET额外公开可选extraction_token_usage，详见[数据模型](../data-model.md)；不新增API或权限。私有去重表与内部事件不公开。

同一行显示“解析 token：{total}”/“Parsing tokens: {total}”，按语言格式化整数；提示展示“输入：{input}；输出：{output}”及英文对应。部分缺失显示“解析 token：{total}（统计不完整）”；全部未知/字段损坏/历史缺失显示“解析 token：未记录”。未开始显示“尚未开始”。完整0与未知不得混同。

前端只消费任务汇总，不重新解析调用日志、估算、写回或另发模型请求；按原状态刷新加载增量，终态值固定。长文件名及窄屏允许指标换行且不扩大卡片操作边界。
