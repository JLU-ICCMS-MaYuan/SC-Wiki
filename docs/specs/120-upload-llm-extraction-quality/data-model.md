# 材料家族全文判断的数据模型增量

`paper.material_families[]` 沿用论文级多选：现有目录项为 `{id, name, status="confirmed"}`，确实无法归入目录的新名称为 `{id=null, name, status="pending"}`。解析不创建正式目录；正式身份由既有审核事务决定。

上传草稿 JSON 的 `material_family_assessment` 由服务端生成，保存 `status`、候选 `families[]`、简短 `reason`、已定位 `evidences[]`、`source_hash`、`rule_version` 与 `model`。`material_family_error` 记录 `catalog_unavailable`、`classification_failed`、`insufficient_evidence` 或空值，用于校对提示。两者属于草稿及其持久恢复快照，不新增表列；客户端只能修改 `paper.material_families[]`，不能为新值伪造模型判断。

字段核对继续保存 `item_key`、`content_hash`、`source_hash`、`status`、`reason`、`ai_reason`、`source_kind` 和本文引句。当前分类与分析候选一致才可引用其理由；人工改选、来源变化或规则版本失效后旧判断只留历史。`supported` 需同时有可定位本文依据和具体判断理由；理由不替代审核员确认。

## 2026-10-12 生成候选与字段诊断

`generation_issues[]` 位于上传草稿 JSON：每项保存 `field`、稳定 `code`、可操作的 `message`、当前值与来源版本的哈希；错误码区分 `main_unread`、`source_absent`、`model_missing`、`quote_unlocated`、`invalid_format`、`candidate_missing`、`conflict`。原有字段仍是正式可编辑值，诊断不另建 Paper 列。

私有 `generation_attempts.json` 以任务/字段/尝试序号记录候选摘要、模型/提示词/来源版本、质量门结果、调用耗时和可获得的 tokens；原始 PDF、密钥及内部思维不进入普通日志。人工改值后旧尝试仅作历史，核对内容哈希失效。

科学候选统一保留 `file_id`、角色、页/块（存在时）、原文引句、材料、相、压力、方法、条件和原值；#114 的几何定位只在具备 Document IR 的路径必填，`legacy` 保留文本层证据等级。
