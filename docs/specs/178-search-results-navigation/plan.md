# 实施计划：检索双视图与详情导航

**Issue**：[＃178](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/178)；日期：2026-10-29；需求：[spec.md](spec.md)。

## 摘要

按检索条件→匹配状态／独立结构→按论文归并或按状态列表→同页切换→新标签详情→来源恢复的顺序重构。用户已回复“开始实现”，按本文复核后实施；实际证据见validation.md。

## 技术上下文

- 语言与依赖：React 19.2、React Router 6.28、MUI 7、TypeScript 5.6、Vite 5；Go 1.25、Gin／GORM 1.31、MySQL；Python结构读取API继续复用。
- 存储：现有papers、material_states、property_modules／records、structure_models和paper_structural_records；浏览器URL保存导航，不新增数据库表或迁移。
- 测试：Go查询及隔离MySQL集成、Vitest宿主行为、真实路由浏览器；共享编辑宿主适用时执行两项form-contract。
- 目标：桌面及390px浏览器；本轮无部署。结果单位正确，服务端分页不拉全库给前端；没有额外具体毫秒指标，实施前记录固定夹具请求及渲染基线。
- 约束：mayuan分支、共享工作区保护、显式路径提交；不得推送或变更运行环境。

## 质量门

| 来源 | 要求 | 处理 | 状态 |
| --- | --- | --- | --- |
| 用户最新批注 | 同页切换且默认论文 | URL及宿主契约明确 | 需求明确 |
| #32／#49 | 稳定状态／完整结构／当前批准revision | 只读既有事实集合 | 设计已列，待实现验证 |
| #56／#59／#142 | 旧约束与新需求冲突 | 定向修订并保留历史原文 | 文档取代边界明确 |
| #174 | 表单合同与真实宿主 | 不增科学编辑逻辑；改共享宿主必须跑合同 | 待实际改动判断及执行 |
| 实施授权 | 用户明确要求开始实现 | 已重新核对Plan、原文及真实字段，记录授权 | 已核对 |
| Issue关闭门 | 远程Spec真实可访问 | 本地路径已登记，未推送 | 保留未完成，不自行push或关闭 |

## Feature文档结构

spec.md、plan.md、research.md、data-model.md、quickstart.md、tasks.md、contracts/search-results.md、contracts/navigation.md、checklists/requirements.md、assets/images.json及六张原图。

## 源代码结构与职责

- `goserver/handlers/papers.go`、拟新增`goserver/handlers/search_results.go`、`goserver/main.go`：候选查询、同一条件过滤、distinct统计与分页；不改科学数据。
- `backend/api/structural_records.py`：独立结构过滤与准确计数，详情／下载继续复用。
- `frontend/src/pages/SearchPage.tsx`、拟新增`frontend/src/lib/searchNavigation.ts`、`frontend/src/components/SearchResults.tsx`：URL读写、视图宿主与结果摘要展示；删除旧Tc列表／局部详情，不复制权限规则。
- `frontend/src/components/PaperStructuralCollection.tsx`、`frontend/src/pages/StructuralRecordPage.tsx`、`frontend/src/pages/PaperDetailPage.tsx`、`frontend/src/components/PaperEditView.tsx`：结构入口、来源return、只读详情；保留其他编辑宿主改动。
- AppShell、MyPapersList、UploadPage、AdminPage、share、SystemCommunityPage、community下EntryCard／ModelAnswerCard／PaperCommunity／CommentPanel：矩阵导航与评论退役。共享文件按任务串行。
- `goserver/handlers/community_entries.go`及相关读取／写入处理：明确退役kind=comment与回复，不破坏AI问题／答案。

结构选择：Go负责完整聚合与状态事实；前端一个宿主维护query／view；Python保留结构详情与导出。原生链接复用小型导航helper，不引入全局状态库。

## 需求到设计的映射

| 来源 | 组件／接口 | 验证 |
| --- | --- | --- |
| FR-001～002、US1 | searchNavigation、SearchPage、导航契约 | 同页切换和新结果标签分开检查 |
| FR-003～005、007、010～011、017、US1／2 | SearchResults服务端查询、数据模型、接口契约 | 多物性／无Tc／跨页／当前revision MySQL集成 |
| FR-006、018、US1 | SearchResults布局与旧局部详情退役 | 真实1400／390px浏览器 |
| FR-008～009、US2 | 独立结构过滤／来源并集 | 无状态模型、已关联去重、两个入口 |
| FR-012～013、019、US3 | URL状态及合法return | 刷新／后退／迟到响应／外站return |
| FR-014～015、US4 | 导航矩阵及相关宿主 | 矩阵逐项真实点击及未保存保护 |
| FR-016、US4 | 评论宿主及Go接口退役 | 旧客户端读取／写入／ID操作，AI与通知回归 |
| FR-020、全局 | 全部只读主路径 | 请求记录无模型／科学写入 |

## 阶段与依赖

1. 文档核验及技术Plan复核，记录实施授权和独立的远程链接待核验项，检查当前源码和并发范围。
2. 固定1论文／8状态／12Tc与无Tc／独立模型、多页数据，先复现旧故障和查询缺口。
3. 服务端集合查询→URL状态和同页双视图→结构与返回→导航及评论退役。
4. MySQL／宿主／浏览器／适用合同回归，逐FR／SC收敛；实现后才更新Overview／README。

## 复杂度说明

需要服务端集合是因为一页Tc记录不能保证去重数量或无Tc覆盖；需要显式return是因为新标签没有可靠的历史来路。除此之外复用现有状态、模型和权限，不新增业务表、模型调用或跨标签通信。
