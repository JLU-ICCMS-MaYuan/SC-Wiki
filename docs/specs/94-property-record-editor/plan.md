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

## US12 仅设计与 Demo（三行修订）

FR-039～042 / SC-030～032 → 既有 #32/#50/#84/#90 语义核查 → T034～036。只制作独立预览并在 Spec assets 留档，不改 React 生产组件、API、数据库或当前事实 Overview。第一行七个输入；第二行是类型、条件结构核处理和压强；结构家族独占第三行且标签不换行增高。Demo 复用项目颜色与侧栏，输入/显隐/折叠均只在本地；宽屏保持三行，窄屏无重叠。

结构处理默认未说明，不从截图的理论类型反推出 SSCHA；切换来源时仅改变预览的显示和启用状态，理论草稿可恢复。普通静态优化与简谐声子不作同义绑定。正式字段归属、mixed 全面退役已明确，具体退役执行及多结构绑定在后续正式实施中确定，当前不生成迁移任务。

## US13 固定高度交互

FR-043～044 / SC-033～034 → T037～039。结构家族控件使用固定 height/min-height/max-height，内部水平 flex-nowrap 标签轨道与输入；仅轨道 overflow-x:auto，禁止标签/内容换行。新增项后滚动至右端输入处；删除或清空不改变框高。保持页面自身无横向溢出，第三行位于类型/核处理/压强下方。

预览快照只接受三种类型白名单，不将旧混合类型转换为 unknown。mixed 退役是明确需求，不再保留兼容路线；本轮仅更新设计和演示，不借此访问或清理数据库。#109 历史布局增加交叉说明，避免把旧的自然增高验收继续当作最新要求。

## US12/US13 进入实施：独立布局与类型边界

FR-039、043 / SC-030、033 → MaterialStatesEditor 的三行容器与固定高度 StructureFamiliesField → T040：保留现有受控输入及证据锚点；第一行七字段，第二行类型/条件核处理/压强，第三行结构家族。标签在独立水平滚动轨道，输入、清空、删除和来源标签保持；不允许多标签撑高。

FR-040、044 / SC-034 → 三种 state_kind 白名单与统一服务端校验 → T041：拒绝 mixed，不静默改成 unknown；模型、提取、建议、读写、导出及数据库约束同步退役。只读审计显示本机 material_states/structure_models 均为 0，3 份持久化/Redis 上传草稿 mixed 为 0，返修草稿 0；无须删除旧 mixed 科学数据。当前 Alembic 有 0052/0137 双头，新迁移必须以实际图合并，不臆造 down_revision。

T042 的结构归属已确认：每状态一份规范几何。MaterialState.structure_optimization 为 unknown/classical_static/sscha，非理论必须 unknown；独立于声子/EPC。StructureModel.nuclear_treatment 从状态字段映射 unknown/classical_static/anharmonic_quantum，SSCHA 方法事实由状态列明确保存，不占用晶胞标准化 geometry_method。保存时先校验最多一个已确认候选（或一份直接结构），不自动合并不同优化结果；同几何其他表示由现有派生服务提供。StructureModel.material_state_id 增唯一约束。已有证据与附件不删除。返修保留元数据时不得恢复旧 nuclear_treatment 覆盖当前选择。

FR-045～046 / SC-035 → 统一 state metadata 校验与 material_state_values → T042：接通上传归一化、提取模型、建议、人工字段哈希、正式读取、Go 响应、返修、同值比较、谱依赖签名和完整导出。服务端在任何结构写入前拒绝多个确认几何并返回明确分卡错误；前端相同卡第二次采纳禁用并说明。保留待审候选及全部来源。

迁移合并 0052/0137 双头；先检查 mixed、多结构、旧明确结构核处理、非理论优化异常，存在时整体中止并列出数量，不做隐式删除／类型映射。空数据无需 backfill。隔离迁移升级／降级、模型 CHECK 与唯一性验证后再准备业务实例应用。共享工作区基线完整备份，只提交本次文件或分块，使用暂存树的隔离候选验证。

本机应用前发现 start_python 会校验部署版本清单和完整 schema 快照。因此本次同步 Linux/macOS schema_heads 与 local-deploy-schema.json 中两个受影响表，避免迁移后服务因旧清单拒绝启动。其余表结构保持原快照，来自隔离 MySQL 迁移的真实 CHECK 文本用于新增约束，业务迁移后重新执行完整 verify_schema。

真实 API 收尾检查：草稿归一化抛出的 UploadContractError 在部分入口没有局部转换，会被通用 500 接管；由主应用统一转成 400 和字段 issues，保留提交入口已有显式处理，不更改校验或保存顺序。测试覆盖真实 FastAPI 分发，并对本机草稿发出无效类型请求，验证拒绝且原草稿内容未变化。

## US14：DOS 展示简化

FR-047～048 / SC-036 → T045～047。PropertyModuleEditor 按电子模块、property 类型与 dos_fermi 代码选择直接渲染已有 PropertyRecordEditor，跳过记录 Accordion 与定义选择；SchemaDrivenRecordForm 对同一记录隐藏证据摘要，复用通用核心行及保存事件。定义加载失败仍在表单显示，其他记录继续原分支。不改变数据所有权、读取依赖或组件职责，不新增接口和依赖。

## US15：先 Demo 的设计草案

当前只授权设计与展示，不能执行正式实现计划。FR-049～052 / SC-037～039 → T048～050。独立 HTML 使用本地场景切换，不调用 API、不保存到业务草稿；复用 IMG-009 四字段目标并移除复制/重复新增。审计历史备份及复制键，区分事实与提议。

待用户认可后，才设计状态内唯一值的提取/保存校验和候选来源归并合同；不在前端过滤 records 后冒充数据已经修复，也不未经确认覆盖科学内容或证据身份。未来保存接口、历史修复和数据约束细节尚未定案。

## US16 增量：预测 Tc 分行 Demo

本节只授权独立 Demo 阶段；正式实现等待 Demo 评审。第一行 λ／ωlog，第二行名称、类型、配对和代表结果；补充参数在第二行后，计算条件及其补充字段独立。原有全部核心字段单行的设计由本节取代。

独立 HTML 不依赖正式组件或业务 API，示例切换保留各自编辑态，sessionStorage 只保存本 Demo 的版本化预览；恢复示例可清理该预览。使用语义标签、逐行 overflow 和可编辑扩展字段，复用既有配对视觉与宽度行为。配对不一致阻止保存预览，编辑过程中不重排输入组。

验证分行／按钮位置、四个示例、参数与条件互不覆盖、宽度增长回缩、类型切换、复制删除、只读和刷新恢复；窄屏测量页面宽度与各行 scrollWidth。截图、实测值存于 assets，不能当成正式 Worker 或数据库验收。Methods 的后续真实补全复用 #139 的全源上下文／阶段关联和版本保护；本轮不调用模型或改真实任务。

Documentation Impact：本轮仅更新现有 Spec 增量、Plan、Tasks、图片及 Demo 验证；Overview 记录当前功能，不写入待评审行为。Demo 确认后再更新 Research／契约和正式实现任务，并分别确认两份 Issue 的增量正文。

## US17：记录操作 Demo 安排（2026-10-16，设计已认可，暂不落地）

对应 Spec US17、FR-056～059 / SC-043～045。正式实施规划尚未启动，本节只记录已获授权的调查和演示工作。

- 复用 #94 及当前 Spec；代码事实来自 `clonePropertyRecord`、`cloneRecordByKey`、`SchemaDrivenRecordForm`，不访问业务数据。
- 独立 HTML Demo 放在 `assets/record-actions-demo.html`，不引入依赖或正式路由。对比“现有布局”与“建议方案”，各自保留预览状态。
- 常用行用字段滚动区加行右删除按钮组成；预测 Tc 保留 λ/ωlog 前置和 Tc/μ* 淡紫分组，窄容器仅字段滚动。
- 通过真实浏览器点击复制、删除、空白新增、只读和折叠，读取几何尺寸检查对齐与局部滚动；保存截图和观测结果。
- 不涉及持久数据或外部接口变更，当前不更新数据模型与正式表单契约。正式实施须先确认设计，再核对四模块专用表单、共享入口和来源核对回归。

用户已认可 Demo 设计并授权同步 #94，明确“暂不落地”；完整追加正文已同步且读回验证。当前不进入正式实施规划或生产路径修改。

### US16 最新 Demo 修订：方法行和多组配对

依据最新三点原话，方法选择移至原名称位置，顶部使用普通 Tc 标题。新增字段增加空白方法行；每行维护独立方法及任意组数的显式 Tc／μ* 对象，组数不再由数值／范围控制。用稳定方法 ID 隔离行内操作，删除只作用于指定数组项，渲染不重排配对。保留一行／一组的最小空态和只读禁用；新方法与新组合初值为空，不复制论文数值。

本版替代先前数值／范围类型切换的 Demo 交互；v2 会话存储与 v1 分开，旧预览不迁移或删除。动态普通计算条件仍用原扩展编辑器。前端主代码及后端契约不变，正式多结果保存／导出、历史范围转换和跨方法参数适用范围在 Demo 认可后另行设计；不能将演示对象结构当成业务 Schema 已批准。新版证据见 assets/tc-multi-method-validation.json。

## US17 正式实施计划

最新用户原话“开始落地！”已解除 US17 的暂不落地限制。FR-056～059 的当前解释见 Spec 正式实施增量，SC-049～050 → T063～066。

- 新增轻量共享行布局 `PropertyRecordRow`：字段区内部横向滚动，操作区独立且不收缩；复用 MUI 主题与现有输入，不复制表单业务规则。
- `SchemaDrivenRecordForm` 统一构造记录删除按钮，普通记录直接使用共享行；Tc 与稳定性组件通过可选操作插槽放到其主行，次级参数/条件/证据不随操作移动。
- `PropertyModuleEditor` 删除复制回调和属性传递，移除表单 onClone；`clonePropertyRecord` 仍是独立的数据深复制工具，不改变既有模型或历史数据。
- 删除继续经 `deleteRecordByKey` → 既有 onChange/deletedRecordKey 处理。没有新 API、数据库迁移或保存逻辑；独立新增、只读和字段来源定位保持现有契约。
- 更新已有行为回归并覆盖四模块、Tc 与稳定性分支；浏览器使用实际共享组件和隔离样例，不操作业务草稿。仅将本次差异放入候选提交，隔离构建验证其自足性。

正式实施任务只包括本节，不执行 US15 去重或 US16 多方法重构。

## US15：唯一 DOS 与侧栏实施

以用户“认可开始落地”为授权。FR-049～052 / SC-037～039 / T051 → 前后端纯 DOS 规范化、现有开放 payload 来源归档、草稿转换、模块持久化及共享证据侧栏。保留首条稳定身份，复制完整源记录；科学比较忽略身份、证据位置及数据库空默认值，不解析原文数字或转换单位。

同状态写入锁材料状态行并检查请求及未显式删除的现存记录；不同状态分别处理。待决定的空当前值允许草稿保存，正式持久化拒绝。记录来源引用进入已有授权 Evidence 链；归档不创建嵌套字段的重复关联。侧栏只读、原位返回编辑、即时人工说明与现有版本门禁复用。验证包括规范化幂等、非法归档、真实 SQLite 往返、模型不能独自消除冲突、共享表单及隔离源码构建。

## US18：结构折叠 Demo（历史阶段，已由下节正式授权覆盖）

仅制作结构标题与现有物性模块同高的独立 HTML，原生 details 保留折叠内容及选择；上传/空态/模型/数据移入展开体，状态和来源入口保持紧凑。当前默认展开与3Dmol不改；默认收起仅为推荐设计。T068～070 覆盖调查、示例、验证和确认，独立补充文档 structure-collapse-demo.md 记录完整原话和 #103 历史条款。本轮不重开 #103，不增加生产合同或迁移。


## US18 正式实施计划

用户认可默认收起和完整 Demo，授权正式落实。沿用既有候选数据和来源核对，不新增接口或持久字段。StructureCandidatePanel 使用与 PropertyModuleSection 相同的箭头、文字和 40px 标题，将全部详情及上传放进保持挂载的隐藏区；来源文字独立于折叠按钮并绑定当前结构 hash。MaterialStatesEditor 传递只读权限，面板只读时仅保留查看和下载；PaperEditView 用 PropertyModuleSection 包装正式结构详情。

StructureViewer3D 已有 ResizeObserver，在首次隐藏展开时适配有效尺寸，原尺寸重开不 zoomTo；本次先保留此实现，以真实浏览器确认。单元回归覆盖默认收起、空态、候选及只读，浏览器核验实际 3Dmol、来源/键盘、窄屏、选项保留，再用仅含本次增量的隔离源码运行回归和构建。T071 → T072 → T073；按差异精确提交，不纳入其他未提交需求。


## US19：添加入口底部 Demo 计划

仅制作独立 HTML 两状态交互。每卡结构区、已有模块容器、谱展示容器、添加区顺序固定；新增模块插入所属卡模块容器的末尾，添加区保持卡片最后。保留原生 details 节点和输入，避免全卡重绘造成丢值；只读切换仅隐藏动作及禁用输入。空态、谱展示与390px纳入验证；场景切换明确为样例重置。正式落地拟将 PropertyModuleEditor 现有 Select 移到 MissingPropertySpectrumModules 之后，但当前不修改组件。T074→T075→T076，与 FR-069～071/SC-056～058 对齐。


## US19 正式实施计划

用户“认可开始”解除Demo阶段限制。将PropertyModuleEditor既有添加Select原样移动到MissingPropertySpectrumModules之后，不新增包装、样式或数据处理。每状态仍经MaterialStatesEditor独立渲染，复用已有addModule、稳定键与只读判断。运行模块编辑、折叠、谱导航及材料表单回归；独立HEAD归档仅叠加本次位置差异完成构建，并用真实共享组件验证两卡/空态/谱展示/只读/输入保留和390px。T077→T078→T079；排除共享工作区的多Tc等未提交功能。


## US16 正式实施计划与完成

以用户“认可开始落地执行。”为授权；按 [正式实施记录](tc-multi-result-implementation.md) 复用 SchemaDrivenRecordForm 条件与既有单值记录存储。前端适配层处理稳定点身份、旧范围显式拆分和组内共同参数；PropertyModuleEditor 负责跨方法代表互斥与批量删除键。后端转换保护新分组，正式持久化结合未提交的现存记录验证唯一代表及共同条件，锁沿用材料状态行。

FR-060～062 / SC-046～047 → 组合适配、共享组件和逐点代表 → T080～082 → 浏览器记录与 MySQL 往返。条件补空交给 #139 T027～028，远程 Issue 更新与链接验证单独收尾，不以本地提交代替推送。


## US20 正式实施计划

FR-072/073 → ScientificFieldBox + 共用ScientificFieldSettingsDrawer → 预测记录计算条件和逐点Tc参数接入；FR-074 → CalculationConditionFields本地侧栏草稿、稳定扩展键与显式应用；FR-075 → 仅隐藏结构优化扩展、保持原payload与阶段隔离。固定字段保留schema类型，元数据通过现有开放payload保存；共享参数/条件仍由updateTcCommon传播，逐点设置保留在各结果。

T087记录授权与契约 → T088实现 → T089来源/保存/只读/并发保护及窄屏验证 → T090文档和精确提交。隔离验证源从HEAD与本次差异构成，排除其他任务的未提交工作；复验浏览器载荷经过MySQL保存、返修与导出。远程Issue和链接门独立保留，不自动推送。
