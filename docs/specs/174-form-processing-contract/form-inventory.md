# 全站表单入口调查

日期：2026-10-28。当前为代码入口核查，不代表行为验收完成，也不替代 GitHub Issue 状态。

入口来源：`frontend/src/App.tsx`、`frontend/src/LazyRoutes.tsx`。搜索范围包含 pages、components 及路由委托的功能目录；下表按用户入口合并共享子控件，不把每个输入框当成独立表单。

| 用户入口 | 主要代码 | 本轮覆盖状态 |
| --- | --- | --- |
| `/upload/tasks/:taskId` 上传校对 | UploadTaskPage、UploadTaskEditor、MaterialStatesEditor、PropertyModuleEditor | 优先修复与完整验收，尚未实施 |
| `/papers/:id/revise` 返修 | PaperRevisionPage、UploadTaskEditor | 优先修复与完整验收，尚未实施 |
| `/admin/papers/:id/edit` 管理员与超级管理员编辑 | AdminPaperEditPage、MaterialStatesEditor | 两种角色分别完整验收，尚未实施 |
| 上述页面的来源与字段设置侧栏 | EvidenceWorkflow、EvidenceFieldMarkers、ReviewPaperTextField、ScientificFieldBox、ManualEvidenceSection、FieldAICandidate | 首轮科学表单验证范围 |
| 上述页面的结构、谱图子区 | PaperStructuralWorkspace、StructureCandidatePanel、PropertySpectra | 首轮覆盖父表单更新的联动影响，不重写独立编辑器 |
| `/upload` 文件选择及正文角色确认 | UploadPage、MultiFileUploadPanel、UploadRoleReview | 已定位，未做本轮性能验收 |
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

## 待实施时补齐的验收映射

在 Spec 确认后，按入口记录数据所有者、具体保存／提交触发、适用 FR、对应测试及结果。共享组件改动必须回查所有使用方；此清单只记录覆盖事实，未完成行动仍由 #174 管理。
