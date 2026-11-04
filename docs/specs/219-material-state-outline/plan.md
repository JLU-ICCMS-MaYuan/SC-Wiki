# 实施计划：研究材料右侧可折叠大纲

**Issue**：[#219](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/219)；**Spec**：[spec.md](spec.md)；日期：2026-11-04。

## 摘要

PaperMaterialsSection复用materialStateSummary与locateMaterialState；桌面为右侧大纲留宽，来源侧栏位于更高层；按state_key在当前宿主定位，历史无key保留显式位置兼容。
基础大纲已随53c32542实现并完成独立拆分。本轮按用户确认的FR-006/007更新展示布局，科学数据与卡片样式保持。

## 技术上下文

- 语言与依赖：现有TypeScript、React 19、MUI 7、Vite 5；涉及服务端的既有部分为Python 3.12/FastAPI/SQLAlchemy及Go 1.25/Gin/GORM。
- 数据事实来源：状态字段由当前宿主草稿/只读版本提供；state_key是定位身份，#编号只是展示；大纲折叠仅属于界面状态。
- 测试体系：原提交中的Vitest、pytest、Go测试和正式构建隔离API浏览器；拆分阶段只校验文档、哈希和关系；本次布局修改重新执行受影响表单门、变异门、定向用例及浏览器测量。
- 目标平台：现有网页的用户/管理员/超级管理员入口；不改变部署方式。
- 性能目标：保持原功能的局部更新与零无意义写入约束；不新增性能指标或宣称性能优化。
- 规模：限本项目标和实际共用宿主，不扩到其他功能。

## 质量门

| 来源 | 要求 | 本项落实 | 核验边界 |
| --- | --- | --- | --- |
| 用户认可的拆分方案 | 功能独立、需求不变 | 原目标6独立建档，原话及图片保留 | 本轮核对 |
| AGENTS.md / #174 | 不破坏权限、来源及表单局部更新 | 引用原实际宿主及共用门证据 | 承接旧运行，不伪称重跑 |
| 原Spec | 正常与异常路径可追踪 | FR/SC→组件→任务→案例 | 见下表及validation.md |
| Issue/Spec关联 | 远程链接真实可访问 | 仅登记本地路径 | 未推送，待验证 |

## 文档结构与条件产物

spec.md、plan.md、research.md、tasks.md、quickstart.md、validation.md、contracts/ui-and-api.md、checklists/requirements.md、assets/evidence.json。
[data-model.md](data-model.md)记录现有实体与边界，无新迁移。

## 源代码触点

- `frontend/src/components/PaperMaterialsSection.tsx`
- `frontend/src/lib/paperMaterials.ts`
- `frontend/src/lib/materialStateSummary.ts`

### 复用但本轮原实现未改动的宿主

- `frontend/src/components/UploadTaskEditor.tsx`
- `frontend/src/components/MaterialStatesEditor.tsx`
- `frontend/src/pages/AdminPaperEditPage.tsx`
- `frontend/src/components/PaperEditView.tsx`

### 对应用例

- `tests/01_decentralized_uploading/form-contract.test.tsx`
- `tests/02_identity_governance/review-workspace.test.tsx`
- `tests/02_identity_governance/review-workspace-browser.mjs`

结构选择：每个组件或服务仍保持原职责；共享文件按本项功能段落归属，后续同文件修改串行处理。

## 需求到设计的映射

| 需求 | 设计 | 任务 | 验证 |
| --- | --- | --- | --- |
| FR-001 / US1 | PaperMaterialsSection复用materialStateSummary与locateMaterialState；桌面为右侧大纲留宽，来源侧栏位于更高层；按state_key在当前宿主定位，历史无key保留显式位置兼容。 | T002、T003 | SC-001、SC-002与validation.md对应案例 |
| FR-002 / US1 | 沿用本项组件职责，约束见spec.md对应FR | T002、T003 | SC-001、SC-002与validation.md对应案例 |
| FR-003 / US1 | 沿用本项组件职责，约束见spec.md对应FR | T002、T003 | SC-001、SC-002与validation.md对应案例 |
| FR-004 / US1 | 沿用本项组件职责，约束见spec.md对应FR | T002、T003 | SC-001、SC-002与validation.md对应案例 |
| FR-005 / US1 | 沿用本项组件职责，约束见spec.md对应FR | T002、T003 | SC-001、SC-002与validation.md对应案例 |
| SC-003 | 独立证据清单与父子关系 | T001、T004、T005 | 原话/图片/哈希/链接检查 |

## 阶段与依赖

1. 读取并保留原需求、既有实现和验收事实。
2. 将原目标6对应的代码、案例和设计独立登记。
3. 核对文档引用与父子关系；远程Spec仅在另行授权推送后核验。

## 当前功能文档

- `docs/overview/01_Decentralized_Uploading_of_Superconductivity_Data/data-structure-and-form-mapping.md`
本轮只修正文档引用归属，不改变这些说明中的业务事实。

## 2026-11-04 全高与4px留白实施（历史方案，后续已取消悬浮）

目录使用固定定位，顶部/底部各4px；不同宿主存在额外容器留白，仅在横向边界或材料状态数量变化时测量当前首卡片边界，以CSS变量统一计算正文留位，不扫描表单字段；外框用纵向flex布局，标题不收缩，条目区使用剩余高度并内部滚动。桌面正文留位与目录宽度统一计算，以浏览器实际卡片边界验证4px缝隙；折叠后只留箭头并回收正文宽度。材料卡片和导航数据职责保持。

FR-006/007、SC-004→PaperMaterialsSection→T006～T009→真实浏览器边界测量与四宿主表单/变异回归。没有标准键、后端、数据库或模型变更。

## 取消悬浮的实施变更

采用MaterialOutlineLayout统一正常网格排版，桌面左侧内容加右侧240px目录，间隔4px；折叠为40px，未挂载目录不留空栏，窄屏按纵向排列。UploadPage在整个任务内容外提供栏位，内层UploadTaskEditor复用它；返修、审核与详情提供同一布局。PaperMaterialsSection通过React portal把只读导航放入当前工作区栏位，数据仍读取当前宿主，定位锚点留在原宿主，既有科学字段组件不换key、不换状态归属。
移除fixed定位、全局padding规则、ResizeObserver及卡片几何测量。目录高度使用窗口高度计算并限制条目滚动，随整页滚动；任务横条恢复正常排版。
FR-006/008、SC-005 → 两个布局组件及四个宿主 → T010～T013 → 更新的浏览器几何/滚动断言、四宿主表单门与变异门。无API、标准键或持久化变更。

## 右栏常驻的后续调整

保留MaterialOutlineLayout网格和既有portal栏位，仅将桌面栏位设为position:sticky、top:4px、align-self:start，使目录在自身右栏内吸附；展开高度仍为窗口减8px，折叠保留窄箭头，条目内部滚动。窄屏单列继续正常排版，避免整块目录遮挡正文。文件／阶段横条不改，继续随页面滚走。无新事件监听、测量、数据或接口。

FR-006、SC-006 → OutlineColumns右侧栏位 → T014～T016 → 真实浏览器滚动、连续跳转及折叠测量，完整宿主表单和变异门。
