# 数据与生命周期

原范围复用 `scientific_evidence_checks.result/resolutions`、`scientific_upload_drafts` 和 `scientific_evidence_sources.result`。新增 US5 的人工文件证据有独立所有权与清理周期，需要专用持久记录，不与论文原文来源混存。

- 字段身份沿用 `item_key`、`state_key`、`module_key`、`record_key`、结构哈希；数组下标仅用于展示定位。
- 核对项增加 `required`：当前是否有需核对的断言；空可选项为 false，仅展示/建议，不产生提交门禁。字段清单允许无值项目，字段类型不能从 null 推测，使用已知定义。
- 模型候选仍用 `proposal` 的类型化 `values`、`basis_kind`、`explanation`、`evidences` 校验。有效论文推断与通用知识推测会补入主表单；已写入的当前核对结果保存 `adopted_basis`、简短 `ai_reason`、`auto_filled` 和对应内容/来源摘要。后两类不能标为原文直接支持；通用知识可没有引句。
- 采用决定保留建议依据、原值、最终值、操作者、理由及内容/来源摘要。`adopted_basis` 保存已采用的来源性质，不因后续 AI 复核或人工批准消失。
- 核对结果可保留 `proposal_review` 表达对已有建议的合理性判断，与当前值的支持状态分开。
- 上传填写值和核对结果持久保存，提交转接稳定身份。批准复制到永久来源后清理临时核对；旧结果仍可读但不得用于新值批准。
- 空记录和未采用建议必须同样转接/归档，不能因不属于提交门禁而在批准时丢失。
- 旧无新增字段的结果按原文建议处理；没有依据标签的历史人工决定保持人工来源，不推定为通用推测。规则版本更新使需要重核的结果失效，不批量写历史。

历史使用 `history` JSON 列表，存放旧当前值、建议、引用、判断与人工理由，跟随上传转接及 Go 永久归档。来源或内容不匹配的历史不授予当前确认资格。后台复核撤回旧支持资格时，未提交接受草稿恢复 `accepted=false`，保留输入；已完成的人工决定只由明确人工保存更新。

## 新增来源可核验约束（待实施）

对于系统原文与核对结论，现有 `records[].status/reason/evidences/source_kind/provenance/check_mode` 加上 `ai_reason/auto_filled` 足以表达 AI 判断、论文原文及派生来源，无须增加系统来源表。人工修改文件的独立记录见下节。侧栏不显示 `proposal.values` 或 `editable_fields`，主表单是唯一的当前值编辑入口。

- `paper_quote`：当前值为 `supported` 时，至少一条引句必须与当前文件、字段、材料及条件对应并可定位；文件名、引句及 PDF 页码或 TXT/MD 段落定位随结果及转接保留。
- `synthesis`：值可以是对原文的忠实概括，不要求生成文字逐字出现在原文；关键论断仍需相关且可定位的原文片段。没有片段的 AI 理由只能作为待补证线索。
- `derived`：由已核验的输入字段和明确规则组成可复核来源；输入、规则或依赖版本变化使旧 `supported` 失效。
- `contributor_structure`、`paper_inference`、`general_knowledge`、`human_review`：各自保留原来源限制，不转写为 `paper_quote`。人工确认仅表示有记录的人工判断，不伪造论文支持。

规则版本更新后，旧 `supported` 结果可作为历史展示，不自动授予新版本通过资格；空可选字段继续可查看，但“可点击”不表示“有原文支持”。

## 模型归纳理由与当前版本（2026-10-11）

继续复用 `ScientificEvidenceCheck.result` 与正式 `ScientificEvidenceSource.result` 的 `check_mode`、`source_kind`、`reason`、`ai_reason`、`evidences`、`content_hash` 和 `source_hash`，不新增表列。`check_mode=synthesis` 且当前值来自模型归纳或分类时，`ai_reason` 保存可核查的依据到结论说明；`reason` 同时保留核对结论。旧记录没有 `ai_reason` 时，仅当前内容与来源哈希匹配、`reason` 具体有效才可作为当前 AI 理由显示。

用户改值、来源变化或规则过期后，旧理由与引句只进入 `history`，不能为新值背书。作者原列关键词、确定性派生字段与人工修改分别保留自身来源身份及说明；有 AI 理由不自动授予 `supported`，仍须符合可定位本文证据与人工审核门禁。

## 人工修改说明与证据实体（代码实施中，待完整验收）

`scientific_manual_evidence` 每行代表一次字段修改说明，字段如下：

| 字段 | 含义与约束 |
| --- | --- |
| `id`、`target`、`target_id`、`paper_id`、`paper_revision` | 服务端生成的身份及当前上传/返修/论文归属；正式提交时同事务转接并绑定论文版本。 |
| `item_key`、`baseline_hash`、`value_hash`、`source_hash` | 稳定字段身份、修改前后规范化值及原来源版本；只有当前值和来源均匹配的行可满足提交门禁。 |
| `actor_user_id`、`actor_name_snapshot`、`created_at`、`updated_at` | 实际修改者、姓名快照与时间；不能由浏览器任意声明。 |
| `reason`、`no_evidence_reason` | 人工判断理由始终必填于显式提交；没有证据条目时，缺证原因也必填。半成品草稿可暂时为空。 |
| `items` | 受控 JSON 清单：每项有服务端 ID、`kind`（`text` / `image` / `text_file`）、用户声明的来源说明、SHA-256、大小及可选原文件名；文字内容保存在记录中，文件由记录 ID 和条目 ID 定位，不返回磁盘路径。 |
| `status`、`evidence_version` | `draft` / `submitted` / `historical`；理由或证据变化使版本递增，批准事务核对版本后归档。字段再次改变时旧记录只读，不为新值提供依据。 |

图片与文本文件存放在独立 `manual_evidence/{id}/{item_id}` 私有目录。上传完成后先校验实际文件内容和扩展名再保存哈希与元数据；文件路径由服务端 ID 确定，不接受浏览器提供的路径。失败时清理本次暂存文件。无引用的未提交记录可随任务取消清理，已绑定论文版本的文件不受上传任务 TTL 影响。下载和预览只通过鉴权接口按记录 ID 获取。

人工证据始终标记 `human_provided`，不能写入 `paper_chunks`、`paper_evidences` 或模型的论文原文来源列表；审核 AI 的输入中作为独立上下文，保留提交者、来源说明、文件身份和是否实际读取。管理员的正式裁决与该修改说明各自保存，不相互伪装。历史论文原记录不自动补造人工证据。

## 2026-10-11 人工 PDF 与路径状态

`items[].kind` 增加 `pdf`，沿用 `filename`、`media_type=application/pdf`、`source_description`、SHA-256、大小与 `ai_read_status`；文件仍按记录 ID 和条目 ID 保存在私有目录。旧 `text` 条目只读兼容。来源说明由经校验的文件名生成，不要求新用户输入。超过 20 页、提取文本超过 2 万字或没有文本层的 PDF 可供人工预览，但审核 AI 保持未读。

当前编辑路径由持久数据推导：存在有效 `items` 为“提供证据”；无附件且 `no_evidence_reason` 非空为“不提供证据”；两者皆空为尚未选择。切换到提供证据时清空旧缺证理由，切换到不提供证据前移除当前草稿附件。显式提交以服务端实际附件和缺证理由为准，历史条目不计入当前版本。


## US11 依赖与修改语义补充（待确认）

复用现有核对记录的 `dependency`（目标记录的稳定 `item_key`）和 `provenance`，以及物性 `claim` 内材料科学条件。不新增表列。`stale` 表示当前断言或支撑它的真实输入、来源、规则已变化，不能代指同卡片出现任意编辑。没有被影响的记录保留原核对、人工确认与说明；迟到响应不能为新断言恢复旧资格。

元素数的直接输入为化学式；符合报告符号标准映射的群号和晶系依赖符号；单位换算值依赖对应原始字段。材料身份与物性科学条件属于各自断言上下文，不能把字段值未变与断言未变混为一谈。前端需读取已有可选依赖，按稳定身份映射到当前路径；旧记录缺失元信息时使用已核实规则，不以数组下标作为身份。
