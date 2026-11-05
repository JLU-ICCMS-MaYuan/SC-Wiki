# 数据与版本

现有scientific_source_items新增namespace=shared-context-v1的不可变条目，payload包含contract及value。引用形如{shared_context_ref:sha256}，与source_ref分开；ID由契约和值的规范序列化确定。无科学字段或表结构升级。当前字段保存目标、内容/来源hash、field-input-v1及人工决定保持。

上下文包可以包含既有来源引用，expand批量取得所需节点并限制循环；不从其他稿件或当前值补缺失引用。快照只共享不可变来源，不改变历史科学内容和文件权限。

关闭上传工作稿仅清空body，保留id/target/document_key/owner/write_epoch/revision；当前返修、管理员稿及其保存基线不改。精简工具私有备份包含原主键、列值及精确浮点表示，数据库恢复按原值验证。
