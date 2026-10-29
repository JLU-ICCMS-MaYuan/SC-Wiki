# 全站表单入口调查

日期：2026-10-28。当前已完成科学表单的本轮验证，其他入口只完成代码调查，不代替 GitHub Issue 状态。证据见 [validation.md](validation.md)。

入口来源：`frontend/src/App.tsx`、`frontend/src/LazyRoutes.tsx`。搜索范围包含 pages、components 及路由委托的功能目录；下表按用户入口合并共享子控件，不把每个输入框当成独立表单。

| 用户入口 | 主要代码 | 本轮覆盖状态 |
| --- | --- | --- |
| `/upload/tasks/:taskId` 上传校对 | UploadTaskPage、UploadTaskEditor、MaterialStatesEditor、PropertyModuleEditor | 完整宿主及大草稿浏览器验证通过 |
| `/papers/:id/revise` 返修 | PaperRevisionPage、UploadTaskEditor | 完整宿主回归通过 |
| `/admin/papers/:id/edit` 管理员与超级管理员编辑 | AdminPaperEditPage、MaterialStatesEditor | 两种角色分别完整宿主回归通过 |
| 上述页面的来源与字段设置侧栏 | EvidenceWorkflow、EvidenceFieldMarkers、ReviewPaperTextField、ScientificFieldBox、ManualEvidenceSection、FieldAICandidate | 首轮科学表单验证范围 |
| 上传/返修的解析差异侧栏 | ParsingDiagnosticsPanel、parsingDiagnostics、EvidenceRegion | #172增量：主表单只留入口与数量，详情按点击进入右侧栏；90来源完整上传宿主、四宿主既有回归、独立来源快照与真实草稿隔离浏览器验证；原图点击加载，非科学审核入口 |
| 上述页面的结构、谱图子区 | PaperStructuralWorkspace、StructureCandidatePanel、PropertySpectra | 首轮覆盖父表单更新的联动影响，不重写独立编辑器 |
| `/upload` 三类文件选择及历史角色恢复 | UploadPage、MultiFileUploadPanel、UploadRoleReview（仅历史任务） | #179：三个指定区域、单正文/格式校验、五文件三并发、完整 UploadPage 与桌面/390px 隔离浏览器通过；未作全站性能验收 |
| `/auth` 登录、注册与找回密码 | AuthPage 委托 AuthExperience 和 production auth 服务 | 已定位，未做本轮性能验收 |
| `/account` 资料、账号安全 | AccountPage、AccountSecurity、UsernameField | 已定位，未做本轮性能验收 |
| `/search` 检索与筛选 | SearchPage | 已定位，未做本轮性能验收 |
| `/knowledge` 图谱检索与筛选 | KnowledgeGraphPage | 已定位，未做本轮性能验收 |
| `/rag` 对话输入和会话操作 | RagPage、LlmProviderSwitcher | 已定位，未做本轮性能验收 |
| `/tc-predict` 预测输入 | TcPredictPage 委托预测功能组件 | 已定位，未做本轮性能验收 |
| `/share/charts` 图表组合编辑 | share、ChartGroupEditor | 已定位，未做本轮性能验收 |
| `/share/discussions`、讨论详情及回答页 | DiscussionPage、DiscussionAnswerPage、CommunityComposer、ModelAnswerCard | 已定位，未做本轮性能验收 |
| `/systems/:systemKey` 体系社区入口 | SystemCommunityPage 及社区共享组件 | 已定位，未做本轮性能验收 |
| `/admin/community` 社区管理 | CommunityModerationPage | 已定位，未做本轮性能验收 |
| `/admin`、`/superadmin` 管理筛选和治理 | AdminPage、SuperAdminPage、SuperAdminGovernance、NewsManager、DefaultLlmConfigPanel | 已定位，未做本轮性能验收 |
| `/spectra/:collectionId` 谱线编辑与标定 | SpectrumDetailPage、SpectrumWorkspace、SpectrumManualEditor | 已定位，独立谱线交互未做本轮性能验收 |
| `/structures/:recordId` 结构查看与编辑入口 | StructuralRecordPage | 已定位，未做本轮性能验收 |
| 跨页面共享配置及目录控件 | LlmProviderSwitcher、ClassificationAutocomplete、PaperReviewStatusSelect | 已定位，按实际使用页面关联验收，不单独宣称全站通过 |

## 已核实的必要请求示例

`UsernameField.handleBlur` 在失焦后先做本地格式检查，合法时查询用户名可用性。它有明确业务用途，不能因为科学表单输入不应调用模型而删除此请求。异步新旧值保护仍须在该入口的实际验收中检查，当前没有完成此项。

## 科学表单依赖核查

- 上传与返修共享 UploadTaskEditor；管理员及超级管理员共享 AdminPaperEditPage。两宿主均传入动态生成的 reviewFields。
- 材料卡片环境比较包含全局 issues、reviewFields，导致数组引用变化能清空全部缓存。
- PropertySpectraProvider 每次渲染创建新的共享 value，可能推动子区域更新；正式修复须验证其数据依赖及最新回调，不能只稳定引用而使用过期草稿。
- 来源标记同时涉及定位、当前值占位、状态更新、点击入口及动态节点增删；减少扫描时必须保留这些语义。

## 数据所有权、触发与规则映射

| 入口类别 | 当前编辑值归属及业务触发 | 适用约束／验证 |
| --- | --- | --- |
| 上传、返修 | UploadTaskEditor 的 draft；编辑记录变化，停顿自动保存／点击保存；提交才走必要审核 | FR-001–008；form-contract、graph-title-form、paper-field-settings、two-stage-review |
| 两种管理员 | AdminPaperEditPage 的编辑草稿；点击保存与明确人工决定／批准各自执行 | FR-001–008；form-contract 四宿主、paper-field-settings、state-review-convergence |
| 科学侧栏 | 主表单值与设置暂存分开，应用回写当前字段；来源按需加载、主动模型核对及人工决定分开 | FR-002–008；上述门禁与来源状态、最新值、删除重定位测试 |
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

上传、返修、管理员、超级管理员的科学侧栏使用同一字段限定保存回调。宿主仍拥有科学输入，人工依据由 ManualEvidenceSection 草稿持有；全部保存成功后获取字段输入令牌，侧栏核对只传一个稳定字段。其他本地输入不随核对操作保存，等待期间暂停整篇自动保存。真实值、依据、权限、取消及较新结果保护保留；整篇提交与全量复核继续自己的契约。

test:form-contract 已加入 sidebar-field-save、sidebar-field-workflow、sidebar-field-hosts；本轮 79 项通过，mutation 仍为四宿主 8 项检出。MySQL／隔离 Redis 和浏览器验证及六项旧失败的独立基线见 [#177](../177-sidebar-field-review/validation.md)，不据此宣称全站或远端 CI 已验证。

## #172 解析差异增量验证

解析原文与备选属于服务端来源账本；面板仅展示快照，不保存第二份科学值。外部草稿加载/刷新才更新快照，表单输入只更新真实依赖的题录当前值。原图按点击加载，完整记录按需挂载，没有“全部通过”按钮。`test:form-contract`含新增parsing-diagnostics套件，共64项通过；mutation仍验证四宿主8项能检出缓存回退。真实CaH6草稿副本页面在输入期间无请求、无全表扫描、无诊断DOM变化。浏览器API隔离，不代替真实登录的全站端到端验收；详细数据及源码见[#172增量验收](../172-phonon-method-parsing/difference-triage-validation.md)。

2026-10-29：解析详情从主表单移入右侧栏，关闭恢复焦点，定位字段返回当前控件；科学待处理入口有问题时为红色，数量和判定规则不变。完整宿主、真实草稿副本及新问题先失败后通过的证据见[#147 诊断与验证](../147-two-stage-field-review/2026-10-29-flow-and-review-diagnosis.md)，既有独立回归失败与基线单列，不算本次通过。

## #179 用户指定上传文件身份

正文恰好一份，补充材料和结构源数据允许多份，选择位置决定角色；不把文件名或文本样式作为新任务角色权威。选择、移除、错区或重复正文拒绝不发创建/模型请求；上传队列使用稳定文件身份，仍限三路并发。UploadPage 宿主与 1440px/390px 浏览器已验证数量、格式、键盘选择和清单请求。规定的表单契约 79 项及变异 8 项通过；影响回归、独立 HEAD 旧失败基线和真实 PDF 定向验证见 [#179 验收记录](../179-manual-upload-file-roles/validation.md)。不据此声称全站、真实业务写入或整篇 PDF 已验收。
