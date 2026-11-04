# 数据与状态

持久模型、标准字段摘要及后端结果令牌保持原契约。EvidenceRecord 新增 local_modified/manual_pending 两个可选浏览器展示属性，不发送为审核决定、不入科学草稿。local_modified 按当前字段与其摘要值比较，原有效通过版本恢复才可消除本地标记；stale、人工拒绝和输入校验仍独立。manual_pending 按 target/item_key 稳定身份汇总该字段各值版本的未保存人工资料，切换或关闭不丢。

模型处理状态与是否仍有问题分开：review_in_progress 可显示处理中，同时原有问题仍留红；确认的新结果或实际问题解除才更新颜色。后端仍通过内容／来源／适用范围版本决定资格，不读取上述临时属性。
