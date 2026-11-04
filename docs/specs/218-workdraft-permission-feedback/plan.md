# 实施计划：合并重复权限提示并统一禁写状态

**Issue**：[#218](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/218)；**Spec**：[spec.md](spec.md)；日期：2026-11-04。

## 摘要

workdraftAccess按ApiError.code识别；AdminPaperEditPage统一警告和禁写；WorkdraftRefresh/EvidenceWorkflow向宿主报告，非同一权限错误保留原展示。
本项已随53c32542实现，本轮将设计与实施依据拆分归档；不安排新的业务代码开发。

## 技术上下文

- 语言与依赖：现有TypeScript、React 19、MUI 7、Vite 5；涉及服务端的既有部分为Python 3.12/FastAPI/SQLAlchemy及Go 1.25/Gin/GORM。
- 数据事实来源：服务端决定写权限；宿主页持有显示状态，子组件报告结构化错误；科学当前值仍由原工作稿持有。
- 测试体系：原提交中的Vitest、pytest、Go测试和正式构建隔离API浏览器；本轮只校验文档、哈希和关系，不重新执行业务套件。
- 目标平台：现有网页的用户/管理员/超级管理员入口；不改变部署方式。
- 性能目标：保持原功能的局部更新与零无意义写入约束；不新增性能指标或宣称性能优化。
- 规模：限本项目标和实际共用宿主，不扩到其他功能。

## 质量门

| 来源 | 要求 | 本项落实 | 核验边界 |
| --- | --- | --- | --- |
| 用户认可的拆分方案 | 功能独立、需求不变 | 原目标5独立建档，原话及图片保留 | 本轮核对 |
| AGENTS.md / #174 | 不破坏权限、来源及表单局部更新 | 引用原实际宿主及共用门证据 | 承接旧运行，不伪称重跑 |
| 原Spec | 正常与异常路径可追踪 | FR/SC→组件→任务→案例 | 见下表及validation.md |
| Issue/Spec关联 | 远程链接真实可访问 | 仅登记本地路径 | 未推送，待验证 |

## 文档结构与条件产物

spec.md、plan.md、research.md、tasks.md、quickstart.md、validation.md、contracts/ui-and-api.md、checklists/requirements.md、assets/evidence.json。
本项只涉及显示或请求/权限反馈，不改变持久化数据模型，因此不创建空的data-model.md。

## 源代码触点

- `frontend/src/lib/workdraftAccess.ts`
- `frontend/src/pages/AdminPaperEditPage.tsx`
- `frontend/src/components/WorkdraftRefresh.tsx`
- `frontend/src/components/EvidenceWorkflow.tsx`

### 复用但本轮原实现未改动的宿主

没有额外未改动宿主需要单列；共享文件范围见上方。

### 对应用例

- `tests/01_decentralized_uploading/form-contract.test.tsx`
- `tests/01_decentralized_uploading/workdraft-refresh.test.tsx`
- `tests/02_identity_governance/review-workspace-browser.mjs`

结构选择：每个组件或服务仍保持原职责；共享文件按本项功能段落归属，后续同文件修改串行处理。

## 需求到设计的映射

| 需求 | 设计 | 任务 | 验证 |
| --- | --- | --- | --- |
| FR-001 / US1 | workdraftAccess按ApiError.code识别；AdminPaperEditPage统一警告和禁写；WorkdraftRefresh/EvidenceWorkflow向宿主报告，非同一权限错误保留原展示。 | T002、T003 | SC-001、SC-002与validation.md对应案例 |
| FR-002 / US1 | 沿用本项组件职责，约束见spec.md对应FR | T002、T003 | SC-001、SC-002与validation.md对应案例 |
| FR-003 / US1 | 沿用本项组件职责，约束见spec.md对应FR | T002、T003 | SC-001、SC-002与validation.md对应案例 |
| FR-004 / US1 | 沿用本项组件职责，约束见spec.md对应FR | T002、T003 | SC-001、SC-002与validation.md对应案例 |
| SC-003 | 独立证据清单与父子关系 | T001、T004、T005 | 原话/图片/哈希/链接检查 |

## 阶段与依赖

1. 读取并保留原需求、既有实现和验收事实。
2. 将原目标5对应的代码、案例和设计独立登记。
3. 核对文档引用与父子关系；远程Spec仅在另行授权推送后核验。

## 当前功能文档

- `docs/overview/02_Decentralized_Maintenance_and_Verification/literature-and-record-review.md`
本轮只修正文档引用归属，不改变这些说明中的业务事实。
