# 全站表单入口调查

## #239/#240 人工问题窗口

UploadPage/UploadTaskPage的UploadModelActivity挂载独立UploadHumanQuestions；新任务策略默认开启，旧无策略不回填。窗口不修改科学字段契约、侧栏或批准规则；回答作为相关人工材料沿上传、返修、管理员、超级管理员原保存交接链处理。问题/动态/论文先行12项交互通过，四宿主250项和12变异通过；真实新文献等待/答题/局部恢复及五阶段边界见[#239](../239-field-human-question-queue/validation.md)、[#240](../240-human-question-default-integration/validation.md)。刷新以稳定task_id保留编辑器，不用卸载来清缓存。

日期：2026-10-28。当前已完成科学表单的本轮验证，其他入口只完成代码调查，不代替 GitHub Issue 状态。证据见 [validation.md](validation.md)。

入口来源：`frontend/src/App.tsx`、`frontend/src/LazyRoutes.tsx`。搜索范围包含 pages、components 及路由委托的功能目录；下表按用户入口合并共享子控件，不把每个输入框当成独立表单。

#212：`/upload/tasks/:taskId` 增加未匹配流程时的通用结果暂停视图，没有新增科学编辑表单。上传、返修和两种管理员角色共用 `ParsingWorkflowIdentity` 展示服务端流程/表单身份；绑定不属于可编辑科学字段，输入和普通保存不重新判断。四宿主及暂停停止轮询的覆盖见[验证记录](../212-typed-parsing-workflow/validation.md)。

#219：四类科学宿主共享 PaperMaterialsSection 右侧大纲、稳定身份定位；本次全高及4px留白已重跑150项表单门、8项变异检出及生产构建浏览器测量，见[材料大纲验收](../219-material-state-outline/validation.md)。禁止写入但保留查看，见[权限提示验收](../218-workdraft-permission-feedback/validation.md)。 科学字段右侧栏功能设计、原话及历史已迁移至 [#221](../221-scientific-field-sidebar/spec.md)，本处不再独立维护。
#216的个人页检查区和独立工作区只改变列表分页与导航，不新增科学值输入入口。初始三项沿用53c32542的实际宿主/浏览器结果；#219后续全高布局的新运行另记，不冒称其他子项重新验收。

#236：共享材料卡增加结构/物性拆分预览及一次确认；四宿主取消、保存、稳定身份与来源保持已通过，完整表单237、变异12项、字段契约通过。5项额外覆盖陈旧预览/权限和邻卡保护；GPT原任务普通网页确认保存重开及其他51状态不变已留证。见[拆分验收](../236-split-structure-property-state/validation.md)。本项不新增科学标准字段或审批步骤。

| 用户入口 | 主要代码 | 本轮覆盖状态 |
| --- | --- | --- |
| `/upload/tasks/:taskId` 浅度论文编辑及启动模式选择 | UploadPage、UploadParsingModeChoice、UploadTaskEditor；沿原字段差量存储，不请求来源核对 | #241：真实编辑器的保存/提交与零核对请求、服务器模式固定、真实来源提取及隔离正式入库/Go匿名搜索通过；深度四宿主沿原回归，不宣称全站性能已验收 |
| `/upload/tasks/:taskId` 上传校对 | UploadTaskPage、UploadTaskEditor、MaterialStatesEditor、PropertyModuleEditor | 完整宿主及大草稿浏览器验证通过 |
| `/papers/:id/revise` 返修 | PaperRevisionPage、UploadTaskEditor | 完整宿主回归通过 |
| `/admin/papers/:id/edit` 管理员与超级管理员编辑 | AdminPaperEditPage、MaterialStatesEditor | 两种角色分别完整宿主回归通过 |
| 科学字段右侧栏功能设计、原话及历史已迁移至 [#221](../221-scientific-field-sidebar/spec.md)，本处不再独立维护。 | 科学字段右侧栏功能设计、原话及历史已迁移至 [#221](../221-scientific-field-sidebar/spec.md)，本处不再独立维护。 | 首轮科学表单验证范围 |
| 上述页面的结构、谱图子区 | PaperStructuralWorkspace、StructureCandidatePanel、PropertySpectra | 首轮覆盖父表单更新的联动影响，不重写独立编辑器 |
| `/upload` 三类文件选择及历史角色恢复 | UploadPage、MultiFileUploadPanel、UploadRoleReview（仅历史任务） | #179：三个指定区域、单正文/格式校验、五文件三并发、完整 UploadPage 与桌面/390px 隔离浏览器通过；未作全站性能验收 |
| `/auth` 登录、注册与找回密码 | AuthPage 委托 AuthExperience 和 production auth 服务 | 已定位，未做本轮性能验收 |
| `/account` 资料、账号安全 | AccountPage、AccountSecurity、UsernameField | 已定位，未做本轮性能验收 |
| `/search` 检索与筛选 | SearchPage／SearchResults，query及view由URL持有 | #178宿主验证同页双视图、过滤与页码恢复、错误重试、迟到响应；2026-11-05增量覆盖正式目录ID／旧别名、四身份状态筛选、身份变化清除旧结果与代表Tc范围；主视图／Tc变化不重查无关独立结构。固定性能基准未验收，不宣称全站性能通过 |
| `/knowledge` 图谱检索与筛选 | KnowledgeGraphPage | 已定位，未做本轮性能验收 |
| `/rag` 对话输入和会话操作 | RagPage、LlmProviderSwitcher | 已定位，未做本轮性能验收 |
| `/tc-predict` 预测输入 | TcPredictPage 委托预测功能组件 | 已定位，未做本轮性能验收 |
| `/share/charts` 图表组合编辑 | share、ChartGroupEditor | 已定位，未做本轮性能验收 |
| `/share/discussions`、讨论详情及回答页 | DiscussionPage、DiscussionAnswerPage、CommunityComposer、ModelAnswerCard | 已定位，未做本轮性能验收 |
| `/systems/:systemKey` 体系社区入口 | SystemCommunityPage 及社区共享组件 | 已定位，未做本轮性能验收 |
| `/admin/community` 社区管理 | CommunityModerationPage | 已定位，未做本轮性能验收 |
| `/admin`、`/superadmin` 管理筛选和治理 | AdminPage、SuperAdminPage、SuperAdminGovernance、NewsManager、DefaultLlmConfigPanel | 已定位，未做本轮性能验收 |
| `/spectra/:collectionId` 谱线编辑与标定 | SpectrumDetailPage、SpectrumWorkspace、SpectrumManualEditor | #165于2026-11-05完成六工具、快捷键、方向/曲线边界与坐标保存回读；124项谱线回归、188项form-contract、12项变异检出及隔离桌面/窄屏浏览器通过，见[验证记录](../165-spectrum-tool-interactions/validation.md)。未做固定性能基准验收 |
| `/structures/:recordId` 结构查看与编辑入口 | StructuralRecordPage | 已定位，未做本轮性能验收 |
| 跨页面共享配置及目录控件 | LlmProviderSwitcher、ClassificationAutocomplete、PaperReviewStatusSelect | 已定位，按实际使用页面关联验收，不单独宣称全站通过 |

## 引用匹配只读入口（#225）

`/upload/tasks/:taskId/citation-matching` 为解析页新标签链接，只读已保存上下游结果，不新增科学编辑宿主。图谱筛选与拖动只改本页视图；解析页仅增加链接和匹配状态，不改变科学字段保存。隔离源码重跑四宿主form-contract 210项和8项渲染／4项漏红变异均通过，见[#225验收](../225-citation-matching-and-static-graph/validation.md)；不据此声称全站性能已验收。

## 已核实的必要请求示例

`UsernameField.handleBlur` 在失焦后先做本地格式检查，合法时查询用户名可用性。它有明确业务用途，不能因为科学表单输入不应调用模型而删除此请求。异步新旧值保护仍须在该入口的实际验收中检查，当前没有完成此项。

## 科学表单依赖核查

四类完整宿主、只读、未应用设置保护、扩展重排和单子项模型请求由field-sidebar-ownership纳入正式form-contract入口； 科学字段右侧栏功能设计、原话及历史已迁移至 [#221](../221-scientific-field-sidebar/spec.md)，本处不再独立维护。
实际草稿只读副本验证11个子项均可达，未定位8→0；相邻35项旧失败在未修改HEAD独立复现，未计作通过。详见[验收记录](../201-field-sidebar-ownership/validation.md)，不宣称真实浏览器或整篇科学核对验收。

- 上传与返修共享 UploadTaskEditor；管理员及超级管理员共享 AdminPaperEditPage。两宿主均传入动态生成的 reviewFields。
- 材料卡片环境比较包含全局 issues、reviewFields，导致数组引用变化能清空全部缓存。
- PropertySpectraProvider 每次渲染创建新的共享 value，可能推动子区域更新；正式修复须验证其数据依赖及最新回调，不能只稳定引用而使用过期草稿。
- 来源标记同时涉及定位、当前值占位、状态更新、点击入口及动态节点增删；减少扫描时必须保留这些语义。

## 数据所有权、触发与规则映射

| 入口类别 | 当前编辑值归属及业务触发 | 适用约束／验证 |
| --- | --- | --- |
| 上传、返修 | UploadTaskEditor 的 draft；编辑记录变化，停顿自动保存／点击保存；提交才走必要审核 | FR-001–008；form-contract、graph-title-form、paper-field-settings、two-stage-review |
| 两种管理员 | AdminPaperEditPage 的编辑草稿；点击保存与明确人工决定／批准各自执行 | FR-001–008；form-contract 四宿主、paper-field-settings、state-review-convergence |
| 科学字段右侧栏功能设计、原话及历史已迁移至 [#221](../221-scientific-field-sidebar/spec.md)，本处不再独立维护。 | 主表单值与设置暂存分开，应用回写当前字段；来源按需加载、主动模型核对及人工决定分开 | FR-002–008；上述门禁与来源状态、最新值、删除重定位测试 |
| 上传文件选择与历史角色恢复 | MultiFileUploadPanel 拥有唯一文件清单，三个区域直接赋予角色；选择/移除无请求，显式上传才创建任务；旧角色确认仅服务历史任务 | FR-001–003/005–009；#179 完整宿主、三并发和浏览器交互通过，详见验收记录 |
| 登录、注册、账号安全 | AuthExperience／AccountSecurity 本地输入；提交及验证码按钮调用对应服务 | FR-001–003/006–009；不套用科学审核流程，未做本轮验收 |
| 个人资料、用户名 | AccountPage 拥有资料编辑值，保存调用 PATCH；UsernameField 失焦后按需检查可用性 | FR-001–003/006–009；未做本轮性能或迟到响应验收 |
| 检索与图谱筛选 | SearchPage／KnowledgeGraphPage 拥有查询条件，查询、筛选或展开触发读取；图谱标记为明确写操作 | FR-001–003/006–009；必要查询不禁用，具体请求合并与并发未验收 |
| RAG、预测 | RagPage／PredictionWorkspace 拥有输入和任务选择；明确发送、润色或预测操作触发服务 | FR-001–003/006–009；未做本轮验收，不泛化科学表单零模型规则 |
| 图表、社区和治理 | 页面与对应编辑组件拥有草稿；提交／管理按钮执行相应业务动作 | FR-001–003/005–009；未做本轮验收 |
| 独立谱线与结构编辑 | 各工作区拥有当前编辑文档或结构；工具操作先修改本地值，保存／处理按工作区契约执行 | FR-001–003/005–009；本轮只验父科学表单的共享更新影响，独立编辑器交互未验收 |
| 共享模型／分类控件 | 值由宿主或现有配置上下文持有，选项变更、提交或显式目录操作按各自契约执行 | FR-001–003/006–009；需关联实际使用方，不宣称单控件通过等于全站通过 |

此清单记录已查明的数据归属和触发类别；未验证项不推断其请求计数或性能正确。新入口及共享依赖变动必须更新清单、适用检查与证据，行动状态由 #174 或后续对应 Issue 管理。

## #177 单字段核对增量

科学字段右侧栏功能设计、原话及历史已迁移至 [#221](../221-scientific-field-sidebar/spec.md)，本处不再独立维护。
宿主仍拥有科学输入，全部保存成功后获取字段输入令牌， 科学字段右侧栏功能设计、原话及历史已迁移至 [#221](../221-scientific-field-sidebar/spec.md)，本处不再独立维护。
其他本地输入不随核对操作保存，等待期间暂停整篇自动保存。真实值、依据、权限、取消及较新结果保护保留；整篇提交与全量复核继续自己的契约。

test:form-contract 已加入 sidebar-field-save、sidebar-field-workflow、sidebar-field-hosts；本轮 79 项通过，mutation 仍为四宿主 8 项检出。MySQL／隔离 Redis 和浏览器验证及六项旧失败的独立基线见 [#177](../177-sidebar-field-review/validation.md)，不据此宣称全站或远端 CI 已验证。

## #180 撤回独立解析差异分类

科学字段右侧栏功能设计、原话及历史已迁移至 [#221](../221-scientific-field-sidebar/spec.md)，本处不再独立维护。
原始区域和备选文本保留在服务端账本；含历史 triage 的草稿可存取，不恢复分类入口或计算。正式表单契约入口以 `parsing-triage-removal` 替换退役的 `parsing-diagnostics` 套件， 科学字段右侧栏功能设计、原话及历史已迁移至 [#221](../221-scientific-field-sidebar/spec.md)，本处不再独立维护。
#177 单字段保存与核对入口继续保留。实际结果和隔离边界见 [#180 验收](../180-remove-parsing-triage/validation.md)。此前 #172 与 #147 的浏览器记录仅证明当时实现，不是当前恢复分类的依据。

## #179 用户指定上传文件身份

正文恰好一份，补充材料和结构源数据允许多份，选择位置决定角色；不把文件名或文本样式作为新任务角色权威。选择、移除、错区或重复正文拒绝不发创建/模型请求；上传队列使用稳定文件身份，仍限三路并发。UploadPage 宿主与 1440px/390px 浏览器已验证数量、格式、键盘选择和清单请求。规定的表单契约 79 项及变异 8 项通过；影响回归、独立 HEAD 旧失败基线和真实 PDF 定向验证见 [#179 验收记录](../179-manual-upload-file-roles/validation.md)。不据此声称全站、真实业务写入或整篇 PDF 已验收。

## #181 方法语义与结构优化详情

StructureOptimizationFields与既有CalculationConditionFields接入上传、返修、管理员及超级管理员。只读、中文组合输入及保存失败重试单列。 科学字段右侧栏功能设计、原话及历史已迁移至 [#221](../221-scientific-field-sidebar/spec.md)，本处不再独立维护。
正式表单入口增加physical-method-hosts，不删除旧回归。新JSON列只做隔离迁移/存取验证，业务库与部署未执行，实际结果及旧失败基线见[验收记录](../181-physical-method-scope/validation.md)。

## 正式交接只读入口（#192）

- /manuscripts/:target/:targetId/handoffs：分页交接元信息列表，不载入全部整稿。
- /papers/:id/snapshots/:snapshotId：共享完整科学表单的冻结只读宿主； 科学字段右侧栏功能设计、原话及历史已迁移至 [#221](../221-scientific-field-sidebar/spec.md)，本处不再独立维护。
- 科学字段右侧栏功能设计、原话及历史已迁移至 [#221](../221-scientific-field-sidebar/spec.md)，本处不再独立维护。


## #203/#204 本轮补充

原有上传、返修、管理员、超级管理员入口继续由完整宿主覆盖；四宿主新增软件分组、直接声子方法、材料状态类型可见性检查。132项表单契约通过，故障注入8项均检出预期失败。科学字段右侧栏功能设计、原话及历史已迁移至 [#221](../221-scientific-field-sidebar/spec.md)，本处不再独立维护。
真实原页面缺失状态类型的问题仍未复现，不能用宿主测试代替该现场验收。

## #209 退回结果保留与字段原文展示

既有sidebar-field-hosts增加四宿主无整包兜底、无蓝底信息框、相关反证与长原文直接显示；field-sidebar-ownership、graph-title-form和form-contract改为在原AI理由区验证真实状态和恢复按钮，不要求已删除的重复摘要／蓝底文案。正式表单门140项通过，8项变异检出；后端真实交接、来源版本与人工决定保持的回滚检查独立记录。实际PDF重新上传、模型与整篇事务边界见[#209验收](../209-return-field-evidence/validation.md)，不把固定宿主夹具冒充整篇科学验收。

## #214 当前稿件状态与只读详情清理

MyPapersList、管理员／超级管理员检查列表及PaperEditView只读详情按当前状态显示；待审稿不重复留在已检查列表。删除旧摘要卡片，保留材料字段与正式关键词数据。本轮未改科学编辑组件、字段契约或保存流程。完整表单188项、12项变异及真实只读API六组浏览器通过；七项相邻旧失败经独立HEAD基线复现，具体范围见[#214验收](../214-rejected-paper-revision/validation.md)，不宣称这些旧失败通过。

#100于2026-11-06更新现有管理员/超级管理员审核动作，未新增科学表单：编辑页及快速审核必须明确选择通过发布或拒绝返修，初始空选择/空意见，失败保留输入；首位领取排他，批准无第二审核人。当前12项两角色中英文宿主交互已纳入form-contract，四宿主210项及mutation通过；来源、真实MySQL竞争和浏览器验证见[#100本轮验收](../100-quick-review-status/validation.md#2026-11-06-单审核员发布验收)。不宣称其他管理表单已覆盖。

## #226共享依赖增量

四宿主继续复用 UploadTaskEditor／AdminPaperEditPage 的正式值与原更新回调，ReviewFieldSettings 使用 UnifiedFieldSettings 补齐类型编辑入口；专用结构控件和只读职责保持。ManualEvidenceSection、manualEvidenceDrafts、EvidenceWorkflow、字段状态投影及后端当前版本决定为本轮共享依赖。交互设计只见[#221](../221-scientific-field-sidebar/spec.md)，颜色只见[#220](../220-field-red-marking/spec.md)。

本轮完整表单225项、12项故障注入、相邻侧栏23项、科学字段锁定及构建通过；真实隔离MySQL20项覆盖并发与发布回滚。正式CaH6页面14个字段操作及提交检查通过，新版批准因并行#225业务库迁移缺失回滚，搜索尚未验收。详细证据及范围见[#226验证](../226-field-workflow-convergence/validation.md)，不把隔离批准替代真实稿发布。


## #228来源标记与#230真实阶段

四宿主复用EvidenceRegion的上下文字符标记和原图覆盖层，开关不改值、不保存、不发起模型或重复区域请求。sidebar-field-hosts新增四种正式宿主的开关交互，原条件上下文和当前值保持；共享树与排除#226增量的隔离树均四项通过。任务页复用既有详情轮询的processing_phase，在报告实际子阶段时显示该动作而不套用固定五步；没有新增轮询请求。完整任务页的阶段、上传/预览相邻测试另行验证。科学字段与当前渲染隔离约束保持。


## #230材料组处理进度

UploadParsingDetail沿原详情轮询展示材料组号、填写/核对/保存动作及已保存状态数；原科学输入、字段身份和四宿主保存合同不变。材料填写和核对在服务端按组串行，模型核对字段限定当前state_key，字段路径维持全稿索引。没有新增科学字段或轮询；阶段/预览9项、四宿主233项、12项变异及字段契约验证分别留证于#230。

#236后续：共享四宿主增加结构卡归并到同条件现有物性卡和结构备注，取消零写、稳定身份与来源及陈旧/权限边界通过；242表单、12变异、字段契约通过。真实GPT草稿归并经#185可空结构保存修复后网页保存重开通过，其他51卡全文不变；未计两模型整篇黑盒通过。详见同一[验收记录](../236-split-structure-property-state/validation.md)。

#226后续枚举空值：四宿主明确选择“未填写”按契约发送null，unknown保持原语义；新增4宿主先失败后通过，完整250、12变异、字段契约及构建通过，实际Safari保存失败/重读留证见[#226](../226-field-workflow-convergence/validation.md)。只更新所选稳定字段，不代表整篇黑盒完成。
