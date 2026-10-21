# 只读调查与复现证据

日期：2026-10-21（Asia/Shanghai）。调查时 HEAD 为 `0632ccd`，工作树有其他任务改动；调用当前工作树中的服务函数，未写业务数据、未调用模型、未重启进程。未捕获浏览器请求体，未做浏览器端到端复现；这些限制保留到实施验收。

## 保存失败已复现

目标任务：`c16cc627a0c04dc8ad4289624d1da80a`，上传者2。
200 GPa的SSCHA字段 item_key：`a0b7616c42ab9691439469d55193b65f756b850358e480032f33da7d7f5c6bcc`。

当前值：

```json
{"key":"sscha.calculation_code","name":"sscha · calculation_code","unit_raw":null,"value_raw":"SSCHA","value_kind":"text"}
```

使用 `upload_snapshot` 构造真实当前字段，调用 `editable_fields` 与 `validate_values(record, {"": record["current_value"]})`；返回 HTTPException，code=`evidence_proposal_invalid`，message=`建议值类型或选项无效：sscha · calculation_code`。逐成员检查发现 `unit_raw=None` 对应 schema 为 `{"type":"string"}`，未允许空值。150/167/200/250/300 GPa共五个SSCHA软件字段均同样失败；其中四个当前仍supported。因此“已经核对通过”不代表“能保存”，与软件拼写大小写无关。

源码依据：

- `backend/ingest/evidence_proposals.py:schema_for` 默认将None推断为字符串；`valid_value`只允许显式nullable的None。
- `editable_fields` 对扩展对象递归生成schema，`field_schema`只给最外层nullable。
- `validate_values` 对整个扩展对象校验，触发截图同一报错。
- `frontend/src/components/EvidenceWorkflow.tsx:valuesFor/saveProposal/accept` 将editable_fields当前值带入proposals保存。

以上为服务函数边界复现；尚未证明截图请求体与全部浏览器调用顺序，不能宣称完整UI根因已验证。

## 旧通过记录真实存在，科学值和来源未变

同一item_key数据库记录：

| 行ID | 状态 | rule_review | 内容摘要 |
| --- | --- | --- | --- |
| 6885 | supported | 有 | 7adfaddb9f96c78962115a7177ac5e25cc15b9de824f06e24c45dfa271fcdf4c |
| 7815 | uncertain | 无 | 4313d62257ba4f751c81ae8d3f2f89d669fe24c979ce9e3b9945583aab8e0c14 |

两行来源摘要均为 `9428b8b9ebb9088fe2bd6c9e69e3798942de93188988c4c63322da27b67e7873`。旧通过事件发生于2026-10-20 18:54:26（北京时间），新核对请求开始于2026-10-21 09:03:20，结果事件为09:07:20。不是缺少旧通过记录。

与本地 `.data/condition-auto-20261020-final/snapshot.json` 中该字段比较，当前claim变化为：

- association_dependencies绑定版本1变2，摘要变化；
- 增加direct_inputs空对象；
- 上下文不再包含crystal_system、material_dimensionality、pressure_raw、pressure_unit_raw、reported_space_group_number。

关键控制实验：分别将 `.data/condition-auto-20261020-final/redis-draft.json` 和当前 `get_draft` 的草稿传给当前 `upload_snapshot(..., parsing_draft=...)`，同一字段产生完全相同的claim和当前摘要 `4313...0c14`，SSCHA值也一致。昨日已存摘要则为 `7adf...df4c`。由此证实：同一旧草稿经过当前代码也会改变摘要，不需要假设用户修改科学值。

相关实现：`property_field_review.review_context`、`review_dependencies`、`association_review.field_binding/effective_associations`、`property_evidence.complete_snapshot` 与 `condition_rules.current_review`。当前读取有历史兼容分支，但有效结论还会重新检查内部review绑定；实施阶段须验证这些环节是否一致，不能只修顶层结果stale。

## 新核对失败的证据

200 GPa当前公开结果为uncertain，顶层stale=false，但来源关联仍显示旧关联问题。理由同时包含：

> 软件依据未明确出现当前软件 sscha，请引用声明该软件的段落，不能只引用下一段的参数

> 原文方法部分明确记载使用SSCHA代码估计非谐效应，且该计算针对LaSc2H24，与当前值一致。

代码由 `condition_rules` 校验结构化软件证据；通用自然语言解释不等于证据已经被正确绑定。因此不能为了消除红框跳过证据检查。应调查如何复用仍可定位的旧证据、纠正本次漏引并保留失败尝试，而不是让用户反复核对同一句科学事实。

## 保存与审核资格的其他待验边界

`evidence_proposals.save_draft` 对非paper_quote来源仍有将supported置false的分支；本批规则通过项目为paper_inference。该分支是需要覆盖的资格一致性风险，尚未通过管理员完整操作链证明发生同样故障，不能写成全部角色的已复现根因。

`frontend/src/lib/evidenceDraftQueue.ts` 明确保留失败请求、暂停自动重试；与截图提示相符，但截图不证明永久忙碌。`.local/log/python.log` 存在proposals 409，而preflight为200；日志没有请求体/字段对应关系，不能把所有409归为本次空单位错误。

## 建议方向与排除方案

- 修复合法对象的读取/保存合同；不要把SSCHA强改大小写或填假单位绕过校验。
- 基于科学语义和必要依赖验证旧证据；不要把旧hash直接换成当前hash强制通过。
- 区分已有有效结论与一次核对运行的成败；不得采用无条件“supported优先”，真实新反证必须生效。
- 以200 GPa浏览器操作链、历史版本升级和跨角色持久化验证闭环；再次运行145项只能作为数据处理步骤，不能作为完整修复验收。

这些是研究建议，尚未定为实现方案。先确定最小后台修复范围；前端状态逻辑若必须变化，按Spec的确认边界处理。

## 可重复的只读验证方式

使用本地项目Python环境，加载 `.env` 后导入 `backend.ingest.property_evidence`、`evidence_proposals`。仅执行 `upload_snapshot`、`editable_fields`、`valid_value`、`validate_values`，查询 `ScientificEvidenceCheck`，以及对两份草稿构造快照比较；不调用 `save_draft`、`save_results`、create_job或重新核对模型。若当前用户继续编辑，后续复现应重新读取并注明当时版本，不将本次摘要当作永远不变的事实。

本轮未保存完整业务快照到Git，历史数据仍在原本地.data备份和数据库中。三张原图在本Spec的assets中，哈希见spec.md；文档及截图远程可读性尚待单独授权推送后验证。


## 补充复现：N(EF)名称保存被空数值槽拦截

用户补充原图IMG-004（spec.md保存完整原话）。截图中数值17.27所在行上方的状态标题未完整显示；下方可见另一个300 GPa状态卡片，不能据此把两张卡片混为一条。当前草稿只读查得17.27记录对应 `state_index=5`、300 GPa、`legacy-property-7`；另一个300 GPa状态为19.61，不能自动互换。

对当前同一任务执行upload_snapshot，检查电子性质dos_fermi普通物性记录：

```json
{"name_raw":"N(Ef)","property_code":"dos_fermi","value_kind":"text","value_number":null,"value_text":"17.27","value_raw":"17.27","unit_raw":"states/spin/Ry/f.u."}
```

只读对照：

1. `editable_fields(record)`生成所有可编辑字段，按当前前端valuesFor方式构造 `{field.path: field.value}`，调用validate_values即报 `evidence_proposal_invalid`，message为 `建议值类型或选项无效：value_number`，与截图相符。
2. 当前value_number为空，schema为number且未允许空值；value_min、value_max、value_boolean、uncertainty、canonical_unit、method_code、method_raw、criterion_code、criterion_raw也含被当前推断规则拒绝的空成员。
3. 仅提交 `{"name_raw":"N(Ef)"}` 调用同一validate_values可通过，说明并非名称字符串本身非法。真实浏览器请求体仍未捕获，这里复现的是现有保存构造路径的服务函数边界。
4. 同一草稿读取到的8条N(EF)普通物性均可重现value_number空值拒绝。167 GPa记录还含嵌套来源对象，其合法可空成员也需遵循一致规则；不得直接放开整个对象、身份和证据改写。

这与SSCHA空单位属于同一层的读取/保存类型合同不一致，但触发字段不同：SSCHA是扩展对象的unit_raw，N(EF)是文本物性未启用的value_number等槽。修复须按字段定义与value_kind区分启用/未启用值槽，不能靠给所有空槽补0或将所有字段nullable来绕过。

截图中17.27/19.61、谐波/非谐波、单位的说明属于另外的科学核对问题，本轮没有重新读原表裁定，没有改名、改类型、改值或采纳模型建议。可保存与可完成科学审核须分别验收；不能以修复保存错误为由消除有根据的科学冲突。

本轮仍为只读调查和文档补充，未修改代码或业务数据，未做浏览器端到端验收。
