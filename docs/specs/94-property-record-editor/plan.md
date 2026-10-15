# 实施计划

输入：[Spec](spec.md)、[Research](research.md)、[数据](data-model.md)、[契约](contracts/record-form.md)。

## 技术上下文与职责

React 19 / TypeScript 5.6 / MUI 的 PropertyModuleEditor 负责菜单、定义选择和记录折叠；
SchemaDrivenRecordForm 负责实验条件单框和旧对象的可读投影。Python upload_jobs 的分段及汇总 prompt
负责逐条提取；现有 convert_legacy_state 已支持 Tc 条目级 experimental_conditions，归一化后进入
property_modules。后端 property_modules.validate_record 与前端 validateRecordClient 校验 description 类型。
MySQL 持久化仍使用 payload_json；测试以 SQLite 执行真实写读。

## 质量门

| 来源 | 要求 | 实现方式 |
| --- | --- | --- |
| AGENTS.md | Spec 先行、中文文档、明确提交范围 | 本目录先形成全部文档，再实现并验证 |
| #90 当前事实 | 条件属于记录、定义不可原地修改 | 使用已有开放对象内 description，不改已发布定义 |
| 用户 | 六方向弱约束、单框、记录折叠 | 两阶段 prompt + 共享输入与 Accordion |
| KISS / DRY / YAGNI | 控制复杂度 | 共用组件实现，不增加接口、数据库迁移或依赖 |

## 需求与验证映射

| 来源 | 设计与数据来源 | 任务 | 验证 |
| --- | --- | --- | --- |
| FR-001 / US1 / SC-001 | definitionLabel 只输出类型和方法 | T002 | 菜单、标题、只读标签、提交版本断言 |
| FR-002、004 / US2 / SC-002 | 单框读取本条 description；旧字段无损保留 | T003 | 旧数据、换行、复制、编辑、只读测试 |
| FR-003、004 / US2 / SC-002 | CHUNK/SUMMARY prompt → normalize → persist | T004 | 模拟 LLM 返回，执行真实下游转换和数据库写读；核对真实调用的 prompt |
| FR-005、006 / US3 / SC-003 | Accordion 用 module/record 稳定键维护交互 | T005 | 多条记录独立切换、键盘、复制删除及错误摘要 |
| 全部 | 文档与完整回归 | T006 | [快速验收](quickstart.md) |

## 阶段与依赖

T001 文档门通过后先写定向行为测试，再执行 T002～T005；同文件改动串行，T006 最后验证和回写。
没有新存储和外部服务依赖，不需要数据迁移。旧对象投影只限实验条件显示边界，不扩散到正常数据库查询。

## Tc 紧凑布局增量

SchemaDrivenRecordForm 将 Tc 核心行交给 TcRecordFields，不再渲染原始记录。
使用容器查询实现 400/640px 断点，避免按窗口宽度判断窄卡片。普通物性保持原表单。
TcNumber 保留本地输入文本，完整合法值写入规范数值，清空或临时非法输入写入 null，
避免后台继续接收旧值；本组件发出的更新不重置输入文本。
propertyModules 统一生成当前 Tc 的兼容 value_raw/unit_raw，在表单加载、编辑及应用核对建议时同步，
不自动从 raw 反推已清空的值。后端 validate_record 对有效 Tc 同步兼容字段后计算校验和，
覆盖上传、管理员、导入及核对建议的保存通路。evidence_proposals 的 expected_claim 使用同一
后端转换规则，核对候选不再编辑派生的 raw/单位，避免保存后精确内容确认失败。
数值和范围使用 K，文本和布尔不保留旧单位。
此规则仅在传入记录的归一化/保存过程中应用，不批量更新数据库或抹除审计历史。
共享校验在上传草稿保存及管理员两段保存之前阻止无效 Tc；现有提交校验复用同一规则。
PropertyModuleEditor 的 Tc 摘要直接读取规范值，字段锚点及 record_key 不变。

| 来源 | 实现与事实来源 | 任务 | 验证 |
| --- | --- | --- | --- |
| FR-007、008 / SC-004 | TcRecordFields、共享记录表单 | T007、T008、T012 | 浏览器容器宽度与单入口断言 |
| FR-009、010 / SC-005 | 本地输入文本、现有规范值列、共享校验 | T007、T009 | 用户输入、保存请求和持久化往返 |
| FR-011 / SC-006 | 字段锚点、稳定记录键、现有核对工作流 | T010、T011 | 管理端/上传/只读回归与生产构建 |

依次完成文档、行为回归、组件和保存校验、浏览器及后端验证、总览与 Issue 回写。

用户最新澄清对应 T012～T014：先将旧保留原始值测试改为覆盖当前值的失败测试，再实施
前端单入口、前后端同步和核对兼容，最后保存往返、文档回写与独立提交检查。

## 2026-10-15：配对单行实施

1. `tcParameters.ts` 负责读取标量/旧包装参数、μ* 范围扩展，生成单一参数写入和两组值的规范化补丁；位置保留在组件本地，不作为持久化顺序。
2. `TcRecordFields` 复用数字文本编辑器，λ/ωlog 前置；预测范围的两组输入放在同色、无边框背景中。以内部局部滚动替换旧容器多列断点，普通物性不变。
3. `SchemaDrivenRecordForm` 排除已提升的三个参数与 μ* 范围扩展，只渲染其余参数，保留其原数组路径以兼容证据定位。
4. μ* 标量沿用 `payload.parameters.mu_star`；范围沿用 `parameters.extensions` 中 `key=mu_star,value_kind=range,value_min/value_max`，主标量不并存。旧包装值读写保留附加字段，扩展保留稳定键及证据。只填单端允许另一端为 null。
5. 客户端与后端共享各自语言的明确校验：可选参数为空合法、非空必须为有限非负数；范围禁止倒置或标量/范围重复。错误路径锚定实际控件。无新表、迁移、接口或已发布定义修改。

| 需求 | 设计及数据来源 | 任务 | 验证 |
| --- | --- | --- | --- |
| FR-012～014 / SC-007 | TcRecordFields、SchemaDrivenRecordForm | T015、T016 | 实际组件及浏览器几何 |
| FR-015～016 / SC-008～009 | tcParameters、既有扩展、property_modules | T017、T018 | 输入、校验、SQLite 保存重读及导出 |
| FR-017 / SC-010 | 共享表单、稳定路径、Overview | T019 | 核对回归、构建、独立提交 |

不通过改写正在编辑的输入来排序；两组值写入时整体映射到规范上下界，外部记录改变时才重新载入。类型改变清理不适用的 μ* 表示；完整范围切换数值时沿用第一组当前 μ*，其他额外参数和证据保留。测量 Tc 不接收预测参数。

## US6～US9 正式实施计划

先更新 Issue #94 与本目录文档，再依下表实施。共享工作区其他任务先备份，脏文件仅暂存本次补丁；从暂存树生成隔离候选验证，不能依赖尚未提交的 SpectrumWorkspace。

| 需求/验收 | 设计与事实来源/职责 | 任务 | 验证 |
| --- | --- | --- | --- |
| FR-018～025 / SC-022 | AutoGrowingTextField 以真实字体测量；SchemaDrivenRecordForm 的通用核心行、条件行、独立扩展行；实际已发布定义决定适用字段 | T020～021 | 四模块交互、原条件/证据保留、浏览器宽度与局部滚动 |
| FR-028～030 / SC-023 | 自定义热力学记录的版本化 payload；专用组件与前后端共享语义的校验；现有 payload_json 持久化/导出 | T022 | basis 切换、未知/零值、非法值、SQLite 真写读 |
| FR-031 / SC-019 | materialStateSummary 读取现有空间群/化学式/压强，仍以 state_key 标识 | T023 | 零压、缺失、编辑/折叠标题 |
| FR-026～027 / SC-024 | PropertySpectra 仅消费 #137 API；模块摘要按 curve.kind；独立 SpectrumDetailPage 重新鉴权查询，主表单保存成功才导航 | T024 | 混合集合分组、错误/版本/状态不匹配、保存失败、返回与真实路由 |
| FR-032～034 / SC-020、025 | ManualEvidenceSection 复用 #138 prepare/save(true)，统一缺项提示；EvidenceWorkflow 保留原核对禁用条件并解释原因 | T025 | pending 文件自动上传、失败保留、版本变化、旧核对不被强开 |
| 全部 | 三入口集成、Overview、精确提交、Issue 证据 | T026～027 | 定向前后端、构建、隔离候选和浏览器 |

### 存储与边界

热力学复用 record.thermodynamical_properties.custom@1，property_code=custom、非空 custom_property_key；payload.thermodynamic_stability.version=1。basis 为 formation_energy / formation_enthalpy / formation_gibbs / unspecified；cases 按 basis 保存独立 case。每个 case 有 stability（stable/unstable/unknown）、above_hull（可空非负数字）、unit（eV/atom 或 meV/atom）、temperature_k、zpe（included/excluded/unspecified）、decomposition_path、source_description。ΔE/ΔH 温度必须 0；ΔG/未知依据可空，不默认 300 K。切换依据不拷贝另一 case，选择稳定/未知清空不再适用的 above_hull。规范文本列由当前 case 状态同步，仅作为记录摘要，事实留在 payload；不将整谱存为标量。

普通自定义定义是开放 payload：提供可选参数及计算条件的新增入口，不为其注入 Tc 专用参数或固定条件。有 schema 的定义只呈现其声明字段；不改已发布 Schema。

谱摘要/详情独立于 #137 尚未提交的 SpectrumWorkspace；通过小型只读 API 客户端和 provider 接入三入口。路由携带 target/target_id/state_key/curve/collection_version，重新读取服务器列表后核对，详情展示服务器返回的版本、来源、曲线/候选、质量与逐点值并使用相同鉴权下载原图和导出。后端负责 revision/run 绑定及公开裁剪；前端不扩大权限或重算物理积分。目标服务不可用如实显示。返回 URL 仅允许站内路径；编辑入口先调用已有真实保存函数，保存失败停留原页。

人工修改单一主操作“保存并完成”先检查说明、证据选择、文件/缺证原因；调用现有 prepare 保存当前科学值并刷新版本，再保存说明和上传文件。失败阶段明确，保留本地修订；不以人工附件代替原文证据或正式审核。管理员仍保留原正式来源核对完成路径。

## US10：模块折叠增量

FR-035～036 / SC-026～027 → PropertyModuleSection → T028～030。使用共享原生 details/summary 包裹模块内容，缺省不带 open；原生鼠标和键盘交互，折叠内容保留挂载。module_key 保持现有 React 身份，因此表单更新不重置展开状态；只读共享同一折叠控件。模块工具栏与 summary 为兄弟节点，避免删除触发折叠。

PropertyModuleEditor 的标量模块和 MissingPropertySpectrumModules 的仅谱模块复用该包装；记录层 Accordion 保留。模块标题显示已有问题数量和首条摘要，折叠状态不进入 PropertyModuleDraft、payload、API 或导出。原生 details 与已有定位逻辑展开祖先 details 的做法相容。

验证：定向交互覆盖初始隐藏、四模块独立性、输入/嵌套折叠保留、已有顺序保留与只读；已有测试在操作内容前显式展开对应模块。三入口浏览器脚本验证默认折叠后再执行原有编辑/保存/详情回归。

## US11：移除模块移动交互

FR-037～038 / SC-028～029 → PropertyModuleEditor、PropertyModuleSection → T031～033。删除上下移动按钮、图标导入和 moveModule；保留删除空模块使用的 normalizeOrder 及既有 module_key/display_order 合同。模块仍直接按传入数组显示，不引入固定排序或数据迁移。共享折叠标题仅为删除按钮预留必要宽度。

更新原有重排交互测试，改为验证非默认顺序不被改写、无移动入口、默认折叠和空模块删除保持。浏览器三入口追加无上下箭头断言，并复用原保存/折叠/详情回归。
