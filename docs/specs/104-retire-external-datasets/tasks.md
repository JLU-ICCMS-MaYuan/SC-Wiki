# 数据源退役任务

**输入**：[规格](spec.md)、[计划](plan.md)、[决策](research.md)、[数据边界](data-model.md)、[契约](contracts/search.md)

## 阶段 1：准备

- [x] T001 核对 #104 与用户范围，完成 `docs/specs/104-retire-external-datasets/spec.md` 及其余设计产物。
- [x] T002 检查 `docs/specs/104-retire-external-datasets/checklists/requirements.md`、需求映射与 Issue 双向链接。

## 阶段 2：US1——本地探索（P1）

- [x] T003 [US1] 验证 `tests/03_data_search_and_database_discovery/local-search-regression.test.tsx` 覆盖元素、化学式、筛选、分页、详情结构及重试。
- [x] T004 [US1] 核对 `frontend/src/pages/SearchPage.tsx` 删除来源分派后保持本地行为，删除专属详情与文案。
- [x] T005 [US1] 用真实本地 HTTP 与浏览器验证保留查询和详情，将证据写入 `docs/specs/104-retire-external-datasets/quickstart.md`。

## 阶段 3：US2——部署与维护（P1）

- [x] T006 [US2] 验证 `goserver/main.go` 取消接口后的实际响应与保留 Python 代理路径。
- [x] T007 [US2] 核对 `goserver/handlers/papers.go`、`goserver/handlers/external.go` 与 `goserver/models/models.go` 的退役清理，保留共享元素工具。
- [x] T008 [US2] 核对 `docker/compose.yaml` 移除数据挂载且相关配置测试通过，不执行数据库变更。
- [x] T009 [US2] 同步 `docs/overview/`、`docs/diagrams/` 与 `future-plan/`，校验文档链接、SVG 和原型。

## 阶段 4：跨功能回归与收尾

- [x] T010 修正 `tests/01_decentralized_uploading/submit-validation-feedback.test.tsx`、`upload-task-editor-layout.test.tsx` 与 `tests/02_identity_governance/admin-edit-page.test.tsx`、`admin-edit-review.test.tsx` 的预检/提交替身，原业务断言不变。
- [x] T011 执行 `docs/specs/104-retire-external-datasets/quickstart.md` 的完整前端、Go、相关 Python 与构建检查，核对无新增回归。
- [x] T012 回写 `docs/specs/104-retire-external-datasets/quickstart.md` 和相关 Overview，确认本任务提交范围，形成通过文档门与验证门的可提交结果。

## 依赖与覆盖

T001 → T002 → US1/US2 → T010 → T011 → T012。同一共享文件串行执行，不委派并行代理。US1 独立验收本地交互，US2 独立验收接口、配置与说明；两个 P1 故事共同构成本项交付。

| 来源 | 任务 |
| --- | --- |
| FR-001、FR-002、US1、SC-002 | T003–T005 |
| FR-003、FR-004、US2、SC-001 | T006–T008 |
| FR-005 | T009 |
| FR-006、SC-003 | T010–T011 |
| FR-007、SC-004 | T001–T002、T012 |

提交与 Issue 收尾在技术任务完成后按 `AGENTS.md` 与 Issue 管理流程执行；Issue 是交付状态的唯一协作来源。
