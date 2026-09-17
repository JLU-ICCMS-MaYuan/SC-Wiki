# 功能内设计决策

## 实验条件保留对象，内部使用 description

- 决策：新文本写入 payload.experimental_conditions.description。
- 理由：已发布 measured_tc 定义要求 Conditions 为对象，但允许其自由字段；保留对象能兼容现有校验、版本与数据库约束。
- 备选：改为字符串或新建 Schema 版本，都会扩大迁移范围，本需求无需采用。
- 证据：backend/data/form_definitions.v1.json、backend/ingest/property_modules.py。

## 历史对象只在界面边界投影

- 决策：无 description 时把旧六字段及其他非空字段转为可读文本；编辑只新增/更新 description，同时保留原对象中的证据和历史字段。
- 理由：结构化记录可能包含扩展字段与 Evidence，替换整个对象会丢失数据。新记录只生成 description；不为新数据重复填旧字段。
- 备选：批量改库或保存时丢弃旧对象，均无必要且会破坏历史证据。
- 证据：SchemaDrivenRecordForm、tests/fixtures/issue90/form-definition-matrix.json。
- 当前展示以显式 description 为准，包括空字符串；旧字段不反向覆盖新文本。

## 两阶段提取均强调每条记录独立条件

- 决策：CHUNK_SYSTEM_PROMPT 和 SUMMARY_SYSTEM_PROMPT 共用六方向提示；每条实验 tc_results 带 experimental_conditions.description，进入已有模块化转换。
- 理由：只在最终表单变更不能改善 AI 提取；只在汇总时提示可能丢失分段原文事实。
- 备选：增加一次独立 LLM 请求；增加成本且没有必要。当前流水线的内部 tc_results 中间产物继续使用，不扩展公共协议。
- 证据：backend/ingest/upload_jobs.py、backend/ingest/upload_contracts.py。
- 分段缓存契约随提示词升为 8，已有旧缓存会由现有版本判断重新提取，避免直接沿用缺少记录级描述的分段事实。

## 折叠在记录层实现

- 决策：PropertyModuleEditor 每条记录包裹独立 Accordion，默认展开，使用稳定键保留状态，标题显示类型/方法与结果。
- 理由：现有模块层折叠无法只隐藏一条记录；共享组件能覆盖上传、审核编辑和只读详情。
- 备选：按数组下标保存折叠状态会在删除/复制后串位，因此不采用。

## 规范 Tc 是唯一日常数值入口

- 决策：用户最新澄清取消独立原始记录，当前类型对应的值是唯一来源。兼容列随当前值生成，新记录不再填第二份值。
- 理由：双入口增加操作负担，旧提取值不应与人工更正值并存为当前科学数据。仅隐藏区域会留下旧内容和不可见的必填错误，必须同步前后端保存表示。
- 备选：从原始值自动解析及换算需要处理复杂原文，本次不引入。
- 证据：SchemaDrivenRecordForm 的原始值和数值事件、property_modules.validate_record、用户确认方案。
- 决策：临时非法文本留在组件，模型值为 null；保存前共享校验阻止请求。合法零值使用显式空值判断，不能用真值回退。
- 理由：上传和管理端使用按钮发起请求，不能仅依赖原生表单 validity；同时防止自动保存或核对完成提交旧数值。
- 前端在现有记录归一化及编辑边界同步，后端在记录校验和持久化边界重新生成兼容值。
  数值/范围单位 K，文本/布尔单位空；不更改稳定键、代表唯一性、版本失效及人工核对草稿规则。
  旧字段错误在界面映射到当前值控件，不能出现已删除控件的报错或核对入口。
- 核对候选不再提供 Tc 的 value_raw、unit_raw、canonical_unit 独立编辑。
  prepare/finalize 的预期内容也必须同步兼容表示；只在实际保存时更新 raw 会造成
  “保存成功但核对绑定失败”。该边界以 expected_claim 与真实保存后断言比对验证。
