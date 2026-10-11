# 材料家族全文判断的数据模型增量

`paper.material_families[]` 沿用论文级多选：现有目录项为 `{id, name, status="confirmed"}`，确实无法归入目录的新名称为 `{id=null, name, status="pending"}`。解析不创建正式目录；正式身份由既有审核事务决定。

上传草稿 JSON 的 `material_family_assessment` 由服务端生成，保存 `status`、候选 `families[]`、简短 `reason`、已定位 `evidences[]`、`source_hash`、`rule_version` 与 `model`。`material_family_error` 记录 `catalog_unavailable`、`classification_failed`、`insufficient_evidence` 或空值，用于校对提示。两者属于草稿及其持久恢复快照，不新增表列；客户端只能修改 `paper.material_families[]`，不能为新值伪造模型判断。

字段核对继续保存 `item_key`、`content_hash`、`source_hash`、`status`、`reason`、`ai_reason`、`source_kind` 和本文引句。当前分类与分析候选一致才可引用其理由；人工改选、来源变化或规则版本失效后旧判断只留历史。`supported` 需同时有可定位本文依据和具体判断理由；理由不替代审核员确认。
