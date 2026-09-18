# 数据模型

## paper_revision_drafts

- paper_id：主键，引用论文，物理删除论文时级联删除草稿。
- owner_id：原上传者，引用用户。
- revision_id：随机 32 位十六进制返修标识，唯一。
- base_revision：起始正式版本；base_fingerprint：正式字段、科学数据、来源及审核状态摘要。
- draft_version：从 1 开始，每次实际保存递增，旧值保存返回 409。
- draft：JSON 草稿；提交后置空。
- submitted_revision：本轮成功送审的版本，未提交为空。
- created_at、updated_at：创建及保存时间，不设置过期时间。

论文行锁先于草稿行锁。相同 paper_id 只能有一份当前草稿，旧轮次提交回执由 paper_history_events.operation_id = revision:<revision_id> 保留。

## 状态与生命周期

论文 rejected → 开始/保存返修（仍 rejected）→ 明确提交 → pending，新版本加一。
再次拒绝后生成新 revision_id；核对结果不跨返修标识继承。普通暂存不写论文修改历史；送审追加 modified，原 reviewed 事件不变。审核字段当前快照清空，旧意见保留在原历史中。

返修 modified 事件的 `classification_snapshot.revision_submission` 保存分类选择及作者角色标记；`previous_definition_events` 保存重建前记录定义事件的完整快照。原结构引用映射到新结构 ID，记录摘要同步重算；未修改结构的原格式与证据关联保留。
