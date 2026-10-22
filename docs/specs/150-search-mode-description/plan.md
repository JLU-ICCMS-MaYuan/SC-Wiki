# 实施计划：元素检索方案说明

**Issue**：[#150](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/150)

**日期**：2026-10-22

**Spec**：[spec.md](spec.md)

## 摘要

复用 SearchPage 的 mode 状态，将按钮名称与说明翻译键放入同一选项列表；直接派生当前说明，不增加状态、请求或后端分支。卡片第一行使用网格三列：标题自然宽度、说明 minmax(0,1fr)、操作区自然宽度；统一 align-items:center。已选元素作为第一行的独立后继行。头部除说明外统一 16px，说明沿用 body2。小于 1600px 的窗口切为单列，操作组允许换行，保持窄屏可读。

## 技术上下文

- 语言与版本：TypeScript ~5.6、React ^19.2.6。
- 主要依赖：MUI ^7.3.5、Vite ^5.4、现有 LanguageContext。
- 数据存储：不适用；沿用 mode 和 selected 页面状态。
- 测试体系：Vitest 现有检索回归；本地浏览器真实页面与布局检查；前端构建。
- 目标平台：桌面及移动浏览器。
- 性能目标：切换时同步渲染文案，不增加 API 调用。
- 约束：仅在 mayuan 工作；仅提交本任务文件；不推送或改变后端逻辑。
- 规模范围：一个页面、两份语言字典、一份功能总览。

## 质量门

| 约束来源 | 强制要求 | 设计如何满足 | 状态 |
| --- | --- | --- | --- |
| Spec | 用户确认后实施 | 完整 Issue/Spec 草案获“开始”确认 | 通过 |
| Overview 与后端 | 说明准确 | 子集、集合相等、超集分别对应三种模式 | 通过 |
| AGENTS.md | 不混入其他任务 | 初始工作树干净；并发出现的后端等其他任务文件保留，仅按本任务路径暂存并核对 diff | 按范围核对 |
| Issue/Spec | 远程双向链接 | 本地路径先登记，未推送时不关闭 Issue | 待远程验证，保留未完成 |

## Feature 文档结构

本目录包含 spec.md、plan.md、research.md、quickstart.md、tasks.md、checklists/requirements.md、contracts/ui.md 和 assets/ 原图。
无新增数据模型，既有页面状态及派生关系记录在界面契约，不单建 data-model.md。

## 源代码结构

- frontend/src/pages/SearchPage.tsx：选项定义、说明及响应式布局。
- frontend/src/i18n/zh/search.ts：中文说明。
- frontend/src/i18n/en/search.ts：英文说明。
- docs/overview/03_Superconductivity_Data_Search_and_Database_Discovery/local-material-search.md：落地后回写。

**结构选择**：在现有组件与字典内完成；无须抽离单用途组件或增加依赖。派生说明保证单一状态来源，按钮与说明共用选项列表避免重复映射。

## 需求到设计的映射

| 来源 | 设计与事实来源 | 任务 | 验证方式 |
| --- | --- | --- | --- |
| FR-001 / SC-002 | SearchPage 卡片头部与 IMG-001 | T003 | 桌面/窄屏浏览器尺寸与截图 |
| FR-002 / SC-001 | mode、共用列表；Go/Python 集合匹配 | T001–T003 | 三种方案及中英文逐一核对 |
| FR-003 / US1 场景 1–3 | 说明不依赖 selected | T003 | 空选择、选择后清除 |
| FR-004 / US1 场景 4 | LanguageContext、换行样式 | T002–T003 | 中英文、窄屏 |
| SC-003 | 既有选择与进入结果处理器 | T004 | 浏览器点击、请求参数与现有回归 |
| FR-005–007 / SC-004 | 第一行三列网格、独立已选行、继承字号 | T006–T008 | 中心点、选中行位置、计算字号与剩余列宽实测 |

## 阶段与依赖

T001 文档与契约 → T002 双语文案 → T003 页面 → T004 验证 → T005 总览与记录。只串行修改共享页面。

无新增复杂度；不使用 effect 同步说明、不为纯文案请求服务器。

## 布局修订

用户在初版后直接指定新的行结构及字号规则，T006–T008 按该指令补充；不重做已通过的后端语义调查或扩展算法范围。
