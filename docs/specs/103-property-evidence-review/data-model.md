# 数据模型

## 统一展示补充（2026-09-17）

不新增实体。材料关系沿用论文级 JSON 列表，单项保留 material、relation 与原有 evidence、quote、page 等属性；编辑两个文本字段不截断来源。研究材料从当前材料状态有序去重汇总，状态类型沿用 state_kind。

结构展示数据仅在前端：当前模型产生晶胞六参数、按行排列的 3×3 晶格矩阵及原子的元素、直角坐标、分数坐标。结构更换时旧结果不得显示，不写回数据库或当成额外论文证据。

## 通用核对项与临时结果

稳定身份由论文字段、材料 state_key、模块 module_key、record_key 或结构身份加字段组成；显示路径按当前表单重新生成。每项保存科学断言、依赖、content_hash、source_hash、rule_version。数值使用规范化十进制，科学内容摘要不含证据补入、显示顺序和内部数据库 ID。

新增 scientific_evidence_checks：目标 upload/paper 及目标 ID、稳定 item_key、版本摘要、完整 result JSON、执行者、时间。result 包括 status（supported/uncertain/unsupported/missing）、reason、suggestion、受影响字段、引句与来源类型。保留旧版本，唯一键防止同一内容重复项；人工裁决按审核员和同版本保存。跨审核员复用 AI 结果但不冒用其他人的裁决。

新增 scientific_evidence_sources：paper_id/revision、item_key、字段路径、内容/来源摘要、正式结果与来源 JSON。与论文级联清理；物性仍关联既有 paper_evidences/property_record_evidences。正式批准将选中结果、来源和人工理由写入历史后删除目标临时核对项。

来源 JSON 区分 paper_quote、contributor_structure、derived。论文引句含当前文件、chunk、原文与页码；附件含真实提交者 ID/名称快照、提供者说明、内容 hash、原始名称和解析依据；程序派生含输入和规则。未知提供者明确为空，不能用论文上传人推断结构来源。

新增 scientific_structure_origins：按目标和结构内容摘要保存首次可证明的认证提交来源；后续保存者不覆盖原始提交者。

新增 scientific_upload_drafts：按 task_id 保存 owner_id、完整 state/draft JSON，没有普通草稿 TTL。上传状态变化同步保存；Redis 丢失时恢复最新状态。正式提交转接和显式删除同时删除该临时快照。

## 生命周期

RQ queued → running → 持久保存 → completed；failed/cancelled 不自动续提。每批完整结果保存前检查取消。Redis 任务可过期，MySQL 完成结果不随之丢失。旧结果可看但只有当前项摘要全部匹配才可批准。

已核对 upload 目标保留草稿与源文件；submit 与论文创建同事务转接结果到 paper 目标，使用稳定身份映射。正式批准与临时清理同事务；失败回滚。目标显式删除按目标清理；旧版本内容没有自动发布资格。

## 可应用建议与接受草稿

新结果包含 proposal（版本、补丁字段/类型/值、来源、支持程度）；与 suggestion 说明分离。按审核员的候选草稿保存于 resolutions 命名空间，含 base 内容/来源摘要、原判断、候选、编辑值、reason、accepted、时间。结构确认不修改结构内容。准备提交返回稳定定位补丁；完成保存后只有当前断言等于预期最终断言且来源匹配才产生新版本结果，decision 留存旧 AI 判断及人工决定。旧草稿保留直至批准同事务清理或显式删除。

## 人工确认来源

沿用现有 JSON 列，不新增表。未核对草稿 status=unchecked、model 为空；按用户 proposals 命名空间保留草稿。decision.human_confirmed=true 表示管理员已明确给出非空理由，绑定 actor_user_id、accepted、final_content_hash/source_hash 与最终值；不等同于 AI supported。永久 result.source_kind=human_review 及 decision 保留原 ai_status/ai_reason、裁决人与理由。重新核对不覆盖同版本已保存草稿或已完成的人工决定。

## 压强编辑与草稿换版

明确清空规范压强时，pressure_value_gpa、pressure_raw、pressure_unit_raw、pressure_min_gpa、pressure_max_gpa 一起为 null；零仍是有效值，临时文本不进入科学数据。修改规范值保留其他原始条件。上传旧契约仅在对应字段缺失时补入，不能覆盖显式 null。

新理由按稳定 item_key 暂存在页面；保存当前表单后刷新 version，再保存当前项草稿。旧版本的 proposal、proposal_draft 与 decision 不作为当前有效结果返回，数据库历史保留。新草稿可在 previous_review 保存修改前判断及其摘要，仅供审计。准备提交忽略未准备的旧版本接受状态；已准备的分阶段操作仍须精确匹配实际值才能继续，不能回填新编辑。

## 材料名与可空化学式关联

`material_states.material_name` 为可空 VARCHAR(255)，和草稿的 `material` 化学式至少一项非空。`superconductor_id` 自 `20260916_0106` 起允许 null；无公式时不创建化学式实体，已有非空关联仍受原复合外键约束。名称进入状态及物性核对内容摘要，但不替代 state_key/item_key。空公式不产生待确认断言；其历史保留，新名称必须单独确认。名称、原始条件、范围和结构家族均参加实际持久内容比较。旧行不回填；降级遇到 null 关联时拒绝。
