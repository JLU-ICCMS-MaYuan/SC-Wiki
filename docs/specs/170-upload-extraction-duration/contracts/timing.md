# 上传计时接口与显示契约

现有 `GET /api/upload-tasks` 和单任务读取公开可选 `extraction_timing`，字段见[数据模型](../data-model.md)。保持现有所有者权限、响应包装、错误码；无新接口。

前端每秒显示累计值加当前运行区间差，文本为“提取内容用时：{minutes} 分 {seconds} 秒”，英文为“Extraction time: {minutes}m {seconds}s”。尚未开始的新任务显示“尚未开始”，旧任务或无效字段显示“未记录”。暂停和终态仅显示已结算秒数。

存在uploading/queued/extracting/reading/summarizing/cancelling/needs_role_review任务时每3秒刷新列表，避免在旧状态上一直计时。失败显示现有错误消息；恢复读取后校正。前台定时器会受浏览器节流，页面再次获焦立即重新读取，不承诺后台标签每秒绘制。刷新不写入任务。

标题旁增加独立文本，宽屏同排、窄屏换行，保留整条打开新标签及复选框、取消、清理的点击边界。多个文件仍显示任务总用时。
