# 论文与记录审核

## 功能说明

通过分级工作台提供论文和关键物性的审核能力，并将图表、快讯和账号治理限制在超级管理员工作台。

## 当前行为

- 研究材料和材料关系在论文基本信息之后固定显示，材料状态类型在每个状态基本区显示；三入口共用展示组件。结构区域左侧三维模型、右侧晶格参数/矩阵/原子位置，窄屏上下排列，详情结构归回所属材料状态。参见[表单映射](../01_Decentralized_Uploading_of_Superconductivity_Data/data-structure-and-form-mapping.md#三入口统一展示)。
- 审核编辑与上传草稿共用紧凑结构附件：宽屏左右各 400px 高，窄屏模型 280px、数据区 400px，长数据内部滚动；模型底部不再重复显示元素图例。整个附件默认展开，可独立收起，文件、状态和精确核对入口始终可达；展开后保留选择和视角，折叠本身不保存数据或使核对失效。
- 来源核对按状态/模块/记录身份定位；结构仅按精确结构摘要匹配，不再用“只有一个可见结构”猜测归属。未选中的结构、已移除状态及未定位字段保留在页面上方核对区域的紧凑清单中，可打开处理，不在页尾输出整份原始值。核对通过只移除问题样式，字段自身保留。

- 审核编辑与上传草稿共用晶系联动：手动选择“未知”时同时清空当前状态的报告空间群符号和编号，重复选择及键盘操作同样生效。保存携带显式空值，失焦与重新加载不回填旧值；之后仍可填写有效空间群恢复正向联动。不在加载时清理历史值，不编辑其他状态或结构附件；核对流程继续识别实际字段变更。（[Issue #105](../../specs/105-crystal-unknown-reset/spec.md)）
- 管理后台可按状态、关键词、材料和年份筛选论文列表，并分页展示。
- 管理员可编辑论文基础字段、摘要、LLM 富化字段和普通物性；物性支持新增、修改与标记删除。
- 管理员论文编辑与上传解析共用书目行：期刊名、年份、期号、卷号、起始页码、DOI，宽度比例为 4:1:1:1:1:4，窄屏保持一行并允许横向滚动。期号为 `papers.issue_number` 可空文本，最长 100 字符；支持保存、详情重载及清空，旧论文为空，无需回填。新增字段进入 Go 管理更新白名单和详情响应，沿用现有修改历史；导入导出保留期号。`pages` 仍保存原页码范围或文章编号。（[Issue #99](../../specs/99-paper-metadata-row/spec.md)）
- 管理员和超级管理员的论文编辑页将 Authors 显示为可增删的姓名标签，输入姓名后按 Enter 或离开输入框确认，直接点击保存也会带上待确认姓名；重复新增不会产生重复标签。关键词与研究方法采用每行一项的多行输入，窄屏上下排列。三个字段不再展示 JSON 列表包装，姓名及描述内部的逗号、引号、括号仍保留。编辑后保存为 JSON 文本列表，清空后重开保持空态；未经编辑的原字符串或空值保持不变，保存失败保留输入以便重试。（[Issue #95](../../specs/95-admin-paper-list-fields/spec.md)）
- 编辑入口为独立页面（`/admin/papers/:id/edit`，`admin` 与 `superadmin` 角色保护），不再是列表页上的弹窗；页面在论文基础信息区维护多个 Material family 和单选 Superconductor type，并接入共享的材料状态编辑组件（`MaterialStatesEditor`，与上传校对页同一实现）：管理员可查看并修改全部材料状态的化学式、维度、`More type labels`、晶系、空间群、压强，及其下的 Tc 列表、普通物性列表与结构附件。任务解析产生的未分配结构候选也在该编辑页中支持分配、确认和排除；#77 Spec 中的“编辑弹窗”表述由 #78 的独立页面实现替代。承载化学式的输入框标签为「化学式」（上传页）/「化学式 (material)」（管理端物性行）。（[Issue #75](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/75)、[Issue #76](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/76)、[Issue #77](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/77)、[Issue #78](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/78)、[Issue #79](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/79)、[Issue #80](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/80)）
- 已落库结构的晶胞表示（惯用胞/原胞）与格式（CIF/POSCAR）按需从落库 CIF 实时生成（`GET /api/rag/papers/{id}/structures/{sid}/representations`），管理端编辑页可自由切换预览并下载对应文件（[Issue #78](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/78)）。
- 科学数据编辑走 Python 端点 `PUT /api/rag/papers/{id}/scientific-draft`（管理员鉴权），语义是整体替换：单事务内按依赖逆序删除该论文当前科学实体后按请求体重建，复用上传提交的校验规则。`pending` 论文原地重建（版本号不变）；`approved` 论文升版重审——`content_revision` 递增、`approved_revision` 清空、状态回到 `pending`，期间不对外公开，重新批准后走既有 publish 链路重建索引。升版由外键级联链支撑：`paper_files` / `paper_chunks` / `paper_evidences` / `material_states` 的 `paper_revision` 随单条 `UPDATE papers` 由 MySQL 级联迁移（[Issue #76](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/76)）。结构附件补传走 `POST /api/rag/papers/{id}/structure-candidates`，只产出候选不写库，随保存一并提交。
- 物性写入只接受 `superconductor_properties` 的真实列（`material_raw`、`name_raw`、`value_raw`、`value_number`、`unit_raw`、`canonical_unit`、`value_min`、`value_max`、`condition_note`）。压强、温度、主记录标记、结构文本与结构格式没有对应列，因此不再被接受，而不是接受后静默丢弃——后者会让管理员以为改动已保存。条件字段属材料状态，不经物性接口修改，以免绕过材料状态自身的校验与审核语义。（[Issue #57](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/57)）
- 管理员可查看、编辑、单篇审核和批量审核论文；论文删除与批量删除只允许超级管理员，且为不可恢复的物理删除（详见下方“论文物理删除”）。
- 管理员和超级管理员的科学数据编辑复用共享记录表单：同一材料状态下的测量 Tc、预测 Tc 和自定义性质均可独立折叠，默认展开；收起时保留结果摘要及服务端校验或定义加载错误提示。记录标题和添加选项隐藏模板版本，测量 Tc 的实验 Conditions 使用一个多行文本框，计算 Conditions 保持结构化输入。旧条件及 Evidence 的保留规则见[上传数据结构与表单映射](../01_Decentralized_Uploading_of_Superconductivity_Data/data-structure-and-form-mapping.md)。（[Issue #94](../../specs/94-property-record-editor/spec.md)）
- 管理员在独立编辑页确认论文级 Material family、论文级单选 Superconductor type、状态级结构家族和材料维度；可认可建议、改选数据库已有项或输入新名称。待审正式关联为空时，页面从审核产物回填上传者确认的多个 family、Superconductor type 与 `More type labels`。分类修改先随编辑保存，再按落库内容核对；批准请求不得夹带未核对的分类。旧 `key_properties.superconductor_type` 与状态级 `superconductor_kind` 都不再参与管理员写入。
- 独立编辑页顶部的已接受建议列表与审核操作区随页面正常滚动，不吸顶或遮挡下方表单；可修改字段和分类后提交审核；元数据区显示论文 ID 和创建时间，不显示物性记录数量。管理工作台论文列表每行操作区域显示可点击进入 `/users/:username` 的上传者，并提供仅显示历史图标的入口；只有管理员和超级管理员可从此读取按时间排序的上传、修改、审核记录。审核事件保留当时操作者和每次审核意见，历史导入论文显示“历史导入，上传者未知”。审核结果统一提供「通过」「退回待审核」「拒绝」三个状态。选择「通过」时，页面先自动保存当前编辑及已接受建议，保存成功后重新读取分类并检查现有核对结果，再提交审核；保存或核对失败不会批准，后端继续执行分类完整性校验。审核请求成功后立即返回当前角色工作台：管理员回 `/admin`，超级管理员回 `/superadmin`。（[Issue #87](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/87)）
- 论文列表和快速审核弹窗不展示物性记录数量；管理员与超级管理员的小锤子快速审核、独立编辑页共用三状态选择器，顺序为「通过」「退回待审核」「拒绝」。快速批准读取最新正式详情；Superconductor type 与材料维度始终使用当前值。仅首次 pending 且论文级 family 尚未落库时，回填提交快照的材料/结构家族，先经科学保存再重读正式分类；状态按稳定 key 或历史唯一化学式匹配，不按数组位置拼接。编辑页批准先自动保存，再重新读取分类并检查现有核对结果。两入口共用分类解析及审核请求构造，均执行现有后端校验。快照 404 时使用正式详情，其他读取错误中止批准并显示原因；拒绝和退回不依赖分类读取。快速审核提交中禁用重复操作，失败保留选项和意见，成功刷新列表及统计。提示明确区分已保存数据和当前编辑选择，需要修改时进入编辑页。快速审核弹窗展示同一套科学数据与问题标记，点击后打开右侧覆盖抽屉查看原文、理由及建议。（[Issue #100](../../specs/100-quick-review-status/spec.md)）
- 目录不提供独立建议队列、重命名、停用、合并或超级管理员二次治理。新名称只在论文批准事务中创建，拒绝或退回不会污染正式目录。
- 管理员与超级管理员保存科学数据时，可按既有别名解析或创建新材料/结构家族目录，并在同一事务中保存论文版本及材料状态关联；普通上传者仍只提交待确认候选。只改论文类型分类或家族也会保存，同值不重建；论文级 family 空列表保存失败，结构家族可以清空，保存后重开不读回旧快照。目录创建、科学保存任一环节失败均回滚。详见 [#100 验收](../../specs/100-quick-review-status/validation.md)。
- 批准论文前检查当前 revision 至少有一个论文级 Material family，并校验各材料状态的元素种类数与主结构唯一性；不完整时返回 `409 classification_incomplete`。全部适用科学数据先经共享核对流程，批准事务内应用证据与人工裁决，再由原有 `validatePaperEvidenceComplete` 检查关联完整性。没有已保存人工决定的无有效出处项目返回 `evidence_missing`，没有已保存人工决定的未核对项目返回 `evidence_check_required`，语义疑点未填写理由返回 `evidence_review_required`，内容变化返回 `evidence_stale`；关联层仍保留 `evidence_incomplete` 防线。批准检查失败时审核事务不改变论文状态和分类；批准前已经成功保存的新目录与科学修改保留待审。批准事件保存分类及证据核对快照。历史数据不自动改写，下次批准时按需核对。
- 新规则核对物性、材料、结构、实验与计算条件、科学分类与叙述，书目信息不逐字段补证。编辑页顶部依次为进行 AI 审核、审核结果、审核意见和提交审核；核对前先保存当前编辑，保存失败不启动模型。提交只读检查核对结果，结果缺失或失效时提示先审核；核对完成不自动提交。字段说明文字入口、右侧覆盖抽屉、建议草稿与上传页共用。
- 管理员可对未核对、无直接原文或 AI 存疑内容，逐条填写推理或专业判断理由并完成确认；服务端保存绑定当前版本的人工决定后允许批准。结构优先论文/附件来源，来源不足时人工确认不伪造提供者；明确记录人工判断及论文未直接支持。确定性派生值由程序复核并保留输入依据，管理员可逐条裁决。
- MySQL 保存全部临时判断与按审核员隔离的理由草稿；批准事务同时保存正式来源、原文和历史，并清理临时判断。失败保留待处理内容，重复批准不重复写历史。权限、自审、内容版本与分类检查始终由服务端执行。
- `paper_history_events` 是上传、修改和审核的唯一追加式历史来源：新上传与论文创建同事务写入 `uploaded`；有实际业务变化的保存写入一条 `modified`；每次实际审核写入 `reviewed` 并保留审核意见。同一次编辑页保存的 Go/Python 两段请求共享 `history_operation_id`，同值保存和同一操作重试不产生重复事件；审核贡献统计仅计 `reviewed`。
- 论文历史弹窗为每条事件显示 `YYYY-MM-DD-HH-mm-vN-审核人-审核简介` 格式的名称。时间沿用浏览器本地时区、精确到分钟；审核人和意见来自该事件快照，空意见显示“未填写审核意见”。上传和修改条目对应位置使用实际操作者及事件类型，历史导入保留上传者未知提示。长意见在名称中合并连续空白并自动换行，原评论正文保留。名称只用于展示，不作为唯一版本标识，也不写回数据库。前端工作台守卫及 `GET /api/admin/papers/:id/history` 均限制管理员和超级管理员，普通用户为 403、未登录 API 请求为 401。（[Issue #93](../../specs/93-paper-version-visibility-and-naming/spec.md)）
- 批量接口不允许批准论文，避免绕过逐篇材料分类确认；批量拒绝和退回仍可使用。
- Go 统一承载 `/api/papers` 列表、`/api/papers/{id}` 详情和白名单 PATCH：匿名仅查看 approved；登录用户可查看 approved 与 pending；上传者额外可查看自己的 rejected 和 `review_comment`；管理员可查看全部及 `admin_internal_note`。
- 无权查看的已存在 rejected 论文返回 403，不再伪装成 404。普通用户不能修改审核状态、文件路径、上传者、审核者或内部备注。
- 工作台首页即导航：顶部页签已移除，功能入口以统计卡片呈现，点击卡片进入对应视图。卡片名称与目标视图名称一致（原“论文总数”改为“论文审核”）。可点击卡片用 `CardActionArea` 渲染，具备按钮语义、可聚焦、可用 Enter 激活；“当前角色”是身份展示，不做成入口。统计未加载完时显示占位符而非 `0`，避免被误读为真实值为零。（[Issue #61](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/61)）
- `/admin` 页面标题为“管理员工作台”，显示“论文审核”和“当前角色”两张卡片。
- `/superadmin` 页面标题为“超级管理员工作台”，复用同一 `AdminPage` 审核状态和业务逻辑，显示六张卡片：用户与权限、论文审核、待审批管理员、图表管理、快讯管理、当前角色；并额外组合图表管理、快讯管理、管理员申请、用户与权限、账号治理和三类审计面板。
- 图表组合和快讯公开读取保持不变，创建、修改、删除和公开状态切换只允许超级管理员。

## 上传者返修与再次审核

管理员拒绝论文后，只有原上传者获得 `can_revise`，可从详情或“我的论文”进入“修改并重新提交”。返修草稿长期保存在 MySQL，保存时正式论文仍为 `rejected`；明确重新提交通过完整校验及来源核对后，同一论文 ID 的版本加一、状态变为 `pending`，上传者恢复只读，管理员按既有规则再次审核。

原拒绝意见及审核事件继续保留，当前审核字段在重新送审时清空。返修分类选择随送审历史持久化，待审快照接口从当前返修版本的历史恢复，不依赖已清理的上传快照。未修改结构的证据和来源文件继续保留；旧管理员核对草稿不会自动成为新一轮决定。并发编辑或审核返回冲突，失败整体回滚、重试不重复升版。

这是对 #76 “没有返修用例时不开放 rejected 科学数据编辑”的补充：新增上传者专用接口，原管理员科学数据接口继续只接受 `pending` 和 `approved`；普通上传者不能用旧论文 PATCH 绕过返修流程。权限、MySQL 事务及再次审核的验收见 [#108](../../specs/108-rejected-paper-revision/validation.md)，用户流程见[上传返修说明](../01_Decentralized_Uploading_of_Superconductivity_Data/pdf-ingestion.md#已拒绝论文返修)。

## 物性补证与人工裁决

管理员、超级管理员的快速审核与独立编辑页共用 `EvidenceWorkflow`，与上传页使用同一后台核对能力。
用户通过独立「进行 AI 审核」按钮启动来源核对；已有核对结果且内容、来源未变时复用，否则显示可取消的
3 秒倒计时，结束后使用当前操作者模型配置在 RQ 中核对。提交审核只检查全量当前结果，不启动模型。
退回待审核和拒绝不要求来源核对。

模型只搜索当前论文及附件，分别提供问题说明和有来源的可应用建议；候选来源及字段类型由程序验证。
同一输入控件聚合问题，点击现有中英文说明文字打开核对；保留红框，不再显示红点。输入框的红色边线沿用浮动标签缺口，不穿过说明文字，标签与数值保持清晰；输入、聚焦、只读及主题背景不改变此规则。没有浮动标签时使用区域标题或文字入口。右侧覆盖抽屉依次展示原内容、问题与改进
方向、可编辑建议。原文默认折叠；数值、枚举、列表和条件按类型编辑，结构附件只确认来源、不生成结构。
管理员编辑页抽屉显示当前表单值，旧结论明确标注对应修改前内容。点击「完成」先保存已经直接编辑的主表单、刷新核对版本，再保存当前值的人工确认草稿；不启动模型或批准，AI 候选仍在提交审核时应用。保留存疑内容或人工改写时需理由。

当前组全部保存成功后右侧栏自动关闭，失败保留侧栏和理由以便重试。完成、关闭按钮、返回、遮罩和 Escape 均保持当前阅读位置，焦点返回实际原字段；顶部已接受列表新增内容不推移正在阅读的字段。已接受项仍可重新打开查看或撤销，迟到请求不关闭后来打开的侧栏。
提交审核时沿用 Go 论文字段保存、Python 科学数据保存，成功后精确核对最终断言与来源才绑定人工决定。
论文信息先保存而科学数据失败时保留已保存修改，重试从未完成阶段继续；批准失败保留待审修改及核对记录。
证据的搜索、选择和关联全部由系统完成，界面不要求用户选择片段或编辑引句。
没有有效出处时可继续查找，也可由管理员逐条说明依据并完成确认；只有填写批准意见而没有保存逐条决定，仍不能放行。重新查找经可取消倒计时重新启动核对，
不会直接返回旧疑点缓存。找到的原文默认折叠供查看，不显示内部文件、片段编号；页码未知时明确说明。
文件不匹配、引句不存在和匹配多处会解释定位问题，由系统重新查找。

两工作台与上传页共用核对进度展示：排队显示动态等待条；开始后展示当前原文组、实际完成组数与百分比，
同时持续更新已等待时间。模型尚未完成一组时不虚增进度；用户可随时取消。

核对与提交分离，取消或离页均不会自动提交；后台完成后持久保存结果。服务端验证管理员
权限、禁止自审、任务归属及预期内容版本。Go 在论文行锁与原审核事务内调用 Python 的只读准备接口，
随后一起保存 Evidence、核对结果、分类、审核状态和历史；模型调用发生在该事务之前。重复审核请求继续使用
原 `review_request_id` 幂等机制。模型配置、超时和服务失败分别提示，不报成表单填写错误。

审核历史的 `evidence_review` 保留模型原判断、原值、AI 建议、用户最终值、来源及人工理由；人工决定不冒充模型判断。接受和撤销草稿按用户、内容与来源版本保存到 MySQL，刷新可恢复；已接受项目可重新打开并撤销。
科学数据编辑以正式详情为准，旧解析快照不会覆盖已保存的物性和证据；分类仍沿既有规则回填。

压强数字区支持点击、全选、删除、小数连续输入和粘贴；点击标签才打开核对。清空规范压强会同时清空原始值、单位、上下限，表示未知；原值留在修改历史中，保存后已删除的压强核对项移除，相关物性随条件变化失效。原始条件可展开编辑，换算或范围不一致时提示管理员核对或说明依据。派生项可从侧栏返回并聚焦主表单。

未保存新值的理由先留在本地，不能发送到旧版本。普通保存刷新核对快照，但不覆盖新理由或更晚编辑；失败保留输入并允许重试。旧候选、接受状态和决定不会自动继承到新值，历史仍保留；已准备的分阶段保存仅在实际值精确匹配时允许恢复。重新查找先保存成功，再调用模型。
编辑页选择通过时自动保存科学数据修改及已接受建议，再读取分类并检查现有核对结果；同版本旧上传快照覆盖新分类的边界见下方已知问题。
（[Issue #103](../../specs/103-property-evidence-review/spec.md)）

## 论文物理删除

超级管理员通过 `DELETE /api/admin/papers/:id`（单篇）和 `POST /api/admin/papers/batch-delete`（批量）执行删除。删除是物理删除：论文行从 MySQL 移除，不写软删除标记，无法恢复。（[Issue #60](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/60)）

- 同一事务内级联清理 15 张关联表，顺序为：`tc_result_evidences`、`structure_model_evidences`、`superconductor_property_evidences`、`tc_results`、`superconductor_properties`、`calculation_contexts`、`experimental_contexts`、`structure_models`、`material_state_structure_families`、`material_states`、`paper_material_families`、`paper_evidences`、`paper_chunks`、`paper_files`、`paper_history_events`，最后删除 `papers`。
- 删除顺序按 `information_schema` 实测的外键依赖拓扑逆序，不可随意调整：例如 `superconductor_properties` 引用 `calculation_contexts`，必须先删前者，否则 MySQL 抛 `Error 1451` 并回滚整个事务，表现为“提示删除成功但数据仍在”。`structure_models` 自引用 `parent_structure_id`，删除前先置空。`material_state_structure_families` 没有 `paper_id` 列，按本论文的 `material_states` 子查询删除。
- 跨论文共享的目录数据不删除：`superconductors`、`material_families`、`structure_families`、`property_definitions`。
- 模块化记录的 `property_evidence_checks` 通过 `record_id` 外键随记录删除清理，不保留指向已删除科学记录的核对缓存。
- MySQL 事务提交后，Go 调用 Python 内部端点 `DELETE /api/internal/papers/{id}/vectors` 与 `DELETE /api/internal/papers/{id}/graph` 清理 Qdrant 向量与 Neo4j 节点。该清理是 best-effort：失败只写日志，不回滚、不改变 HTTP 结果——MySQL 行此时已不可恢复，强制回滚只会制造更严重的不一致。Go 通过 `PYTHON_BACKEND_URL` 定位 Python 服务。
- 批量删除逐篇独立处理，单篇失败不影响其余。存在失败时返回 `206` 与 `failed_ids`；`206` 落在 2xx 内不会触发前端的错误分支，因此前端按 `failed_ids` 判定并提示失败篇数与 ID，而非仅凭 HTTP 成功即报完成。
- 删除成功后清理 `chart:*`、`search:*`、`community:contributions:*` 缓存。

## 工作流程

管理员工作台只请求论文数据并完成筛选、编辑和审核。超级管理员工作台复用这些审核请求，再按所选卡片加载图表、快讯、申请、用户和审计数据；后端路由组独立校验各级权限。

科学数据操作有四个独立结果，不能把核对完成当作论文已批准：

| 操作 | 保存或检查的内容 | 失败时的行为 |
| --- | --- | --- |
| 保存当前编辑 | 保存表单当前值，刷新对应内容与来源版本；相关旧确认失效 | 保留输入，不把旧理由绑定到尚未保存的新值 |
| 进行 AI 审核 | 先保存编辑，再全量复核当前字段、全部已有建议与当前论文及附件，已有通过缓存不跳过，持久保存结果 | 保存失败不调用模型；核对结束不自动提交或批准 |
| 完成人工确认 | 管理员逐条保存理由并绑定当前值；AI 候选仍作为接受草稿，在提交时应用 | 保留理由与建议以便重试；成功关闭侧栏并保持原字段位置 |
| 提交通过审核 | 应用接受的建议，检查最终版本、权限和分类，由 Go 批准事务写入永久来源与历史 | 不自动调用模型；已保存的待审修改保留，批准事务失败不清理临时核对 |

管理员可以对未核对或无直接引句的内容逐条作出人工决定；普通上传者不能使用此权限。
服务端要求理由、操作者、最终内容和来源版本匹配，整篇审核意见不能代替逐项决定。
永久来源区分论文引句、提供者结构、程序派生与人工判断；检索和问答继续保留来源限定，
不能将人工判断写成论文结论。相关规则见[上传数据与来源映射](../01_Decentralized_Uploading_of_Superconductivity_Data/data-structure-and-form-mapping.md)
及[问答引用](../05_Retrieval-Augmented_AI_Question_Answering/streaming-qa-and-evidence.md)。

验收范围见 [#103 验证记录](../../specs/103-property-evidence-review/quickstart.md)：组件和浏览器夹具、
隔离持久化、历史真实 MySQL 回滚与模型核对分别记录。已有本地实现与验收不代表新部署已执行，
也不代表已有论文已被实际批准或远程索引已重新发布。

## 约束

- 所有审核操作需要 active admin 或 active superadmin 身份。
- `review_comment` 在界面称为“审核意见”，用于向上传者反馈；`admin_internal_note` 只允许管理员读取和通过审核接口维护。
- 图表组合管理的前端存在搜索、导入、导出、复制等调用，但当前 Go 路由只注册列表、详情、创建、更新、删除和公开切换。
- `chart_groups` 与 `chart_group_items` 两表此前从未有迁移创建，图表组合功能整体不可用（goserver 持续报 `Error 1146`）；迁移 `20260831_0065` 已补齐建表，功能恢复可用。图表数据点的 `custom_year` 与 `custom_article_type` 此前在创建与更新接口中被静默丢弃，现已收取。
- 用户“删除”已替换为保留历史关系的账号注销；封禁、解封、注销和角色变更要求原因与确认。论文物理删除仍仅限超级管理员。

## 代码与测试

- `goserver/handlers/admin.go`
- `goserver/handlers/paper_evidence.go`、`backend/api/evidence.py`、`backend/ingest/property_evidence.py`
- `frontend/src/components/EvidenceWorkflow.tsx`
- `goserver/handlers/paper_evidence_mysql_test.go`、`tests/01_decentralized_uploading/evidence-workflow.test.tsx`
- `goserver/handlers/paper_deletion.go`
- `goserver/handlers/paper_deletion_test.go`
- `goserver/handlers/stats.go`
- `backend/api/admin_internal.py`
- `goserver/handlers/papers.go`
- `goserver/handlers/classifications.go`
- `goserver/handlers/news.go`
- `goserver/handlers/chart_groups.go`
- `backend/models.py`
- `frontend/src/pages/AdminPage.tsx`
- `frontend/src/pages/AdminPaperEditPage.tsx`
- `frontend/src/lib/paperTextLists.ts`
- `frontend/src/LazyRoutes.tsx`
- `frontend/src/components/PaperEditView.tsx`
- `frontend/src/components/NewsManager.tsx`
- `frontend/src/components/SuperAdminGovernance.tsx`
- `goserver/handlers/admin_review_event_test.go`
- `goserver/handlers/paper_history_test.go`
- `tests/01_decentralized_uploading/admin-paper-classification-review.test.tsx`
- `tests/02_identity_governance/admin-edit-page.test.tsx`
- `tests/02_identity_governance/admin-paper-list-fields.test.tsx`
- `goserver/handlers/admin_paper_list_fields_test.go`
- `tests/02_identity_governance/identity_ui.test.tsx`
- `tests/02_identity_governance/admin-workspace-cards.test.tsx`

## 相关变更记录

- [Epic #37：用户身份、账户安全与分级管理工作台](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/37)
- [Issue #57：物性写入收敛为真实列，不再接受无对应列的字段](../../specs/57-paper-detail-data-parity/spec.md)
- [Issue #60：论文删除改为按外键依赖级联的物理删除](../../specs/60-fix-paper-deletion-cascade/spec.md)
- [Issue #61：工作台导航由页签改为卡片式入口](../../specs/61-admin-workspace-navigation-refactor/spec.md)
- [Issue #62：审核弹窗移除纯阅读性展示内容](../../specs/62-simplify-paper-review/spec.md)
- [Issue #78：管理端审核编辑页独立化并功能对齐提交页](../../specs/78-admin-edit-page/spec.md)
- [Issue #94：物性记录标题、实验条件文本与独立折叠](../../specs/94-property-record-editor/spec.md)
- [Issue #95：管理端论文作者、关键词与研究方法的可读编辑](../../specs/95-admin-paper-list-fields/spec.md)
- [Issue #103：物性证据保留、自动补证与人工裁决](../../specs/103-property-evidence-review/spec.md)

当前值保存支持只填材料名、清空化学式及独立修改原始压强、范围等条件。材料名改动使本状态相关核对失效，旧理由与候选不自动确认新值；删除的字段从当前问题列表移除，重新查找也不再请求该字段。保存失败保留表单与人工理由；完成只写当前版本人工草稿，不自动批准。

## 已知问题

- 图表组合的搜索、导入、导出和复制接口前后端契约仍不完整；本次只收紧现有写接口权限。
- 论文删除对 Qdrant 与 Neo4j 的实际清理效果**待核验**：MySQL 级联删除已在真实库验证（删除后 14 张表清零、全库无 `paper_id` 残留、`superconductors` 保留），但用于验证的论文为 `pending` 状态、从未发布到向量库与图库，两库本就没有对应数据，因此目前只覆盖了“目标不存在时不误报失败”这一边界。需用一篇已 `approved` 且已发布的论文补验。

未核对项目保持 unchecked，输入未核对的派生项不误报 missing。理由和候选在停止连续输入约 500 毫秒后合并保存，关闭/完成/提交时刷新保存队列；失败保留当前输入、暂停自动重试，用户显式重试提交最新值。无模型结果也能创建未核对草稿；草稿不作为 AI 核对缓存。人工确认保留原 AI 状态、理由、裁决人、最终值和内容/来源版本，Go 同事务保存永久 human_review 来源和历史；旧物性关联检查接受本次准备中已验证的人工来源。数据类型、权限、自审和并发约束继续有效。

管理员与超级管理员编辑页的全部数据字段名均可打开来源侧栏，包含无证据和空字段；审核结果、审核意见等操作控件除外。问题解决后恢复普通样式，查看入口及已保存的人工理由继续保留；顶部不再列出逐条已接受记录。全量 AI 复核质疑旧候选时，撤回其尚未提交的旧通过资格，保留输入等待重新确认；后台任务不能覆盖期间保存的新人工决定。采用通用知识推测可进入待审，但正式批准必须逐条填写管理员依据，批准不会抹去推测标识。内容或来源变化的历史仅供参考，不获得当前批准资格。参见 [#109](../../specs/109-field-evidence-and-ai-suggestions/spec.md)。
