# 数据源退役实施计划

**Issue**：[维护事项 #104](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/104)

**Spec**：[spec.md](spec.md)；**日期**：2026-09-11

## 摘要

删除专属纵向路径，复用本地 `SearchRecords` 和论文详情读取。通用路由代理、元素集合工具、物性与结构读取、上传审核业务不变。补齐行为测试及实际 HTTP 验收；仅将失效测试替身对齐 #103 的证据预检契约。

## 技术上下文

- 前端：TypeScript 5.6、React 19、MUI 7、Vite 5、Vitest 2。
- 后端：Go/Gin/GORM，Python/FastAPI/SQLAlchemy；MySQL 为现有关系事实来源。
- 测试：Vitest/Testing Library、Go testing、pytest、实际本地 HTTP 和浏览器。
- 平台：Linux 本地开发与 Docker Compose 部署配置；不执行部署。
- 性能边界：只移除外部请求，不新增数据库查询、轮询或远程依赖。

## 质量门

| 来源 | 要求 | 满足方式 |
| --- | --- | --- |
| 用户与 AGENTS.md | 最小改动、保留其他功能 | 删除专属实现，保留共享读取；测试替身修正不改变业务规则 |
| 用户 | Spec 后继续完成 | 本文档门先完成，再执行剩余任务 |
| AGENTS.md | Issue 唯一状态源 | 使用 #104，Spec 双向链接，不建立本地协作状态副本 |
| 用户已确认分类 | 维护事项 | 保留 type:maintenance，按本次明确要求补齐 Spec |
| AGENTS.md | 验证通过后自动提交 | 前端全量变绿、Go 与相关 Python 通过后仅暂存本任务文件 |
| Overview | 只记录当前事实 | 代码验收后同步，总览不写计划能力 |

## 源代码与职责

- `goserver/main.go`：取消外部和聚合路由；通用代理继续服务其他接口。
- `goserver/handlers/papers.go`：保留本地查询、元素匹配与详情；删除聚合专属逻辑。
- `goserver/handlers/external.go`：删除专属查询。
- `goserver/models/models.go`：删除外部模型，不操作数据库。
- `frontend/src/pages/SearchPage.tsx`：只请求本地记录，保留表格和详情路径。
- `frontend/src/components/AlexandriaDetail.tsx`、`HtscDetail.tsx`：删除。
- `frontend/src/i18n/{zh,en}/search.ts`：删除专属文案。
- `docker/compose.yaml`：移除 HTSC 数据挂载。
- `tests/03_data_search_and_database_discovery/local-search-regression.test.tsx`：搜索行为回归。
- `tests/01_decentralized_uploading/{submit-validation-feedback,upload-task-editor-layout}.test.tsx` 与 `tests/02_identity_governance/{admin-edit-page,admin-edit-review}.test.tsx`：按端点区分预检与最终提交响应。
- `docs/overview/`、`docs/diagrams/`、`future-plan/`：同步退役内容。

## 需求映射

| 来源 | 设计/事实来源 | 任务 | 验证 |
| --- | --- | --- | --- |
| FR-001、FR-002、US1、SC-002 | SearchPage → SearchRecords → 本地物性与论文 | T003–T005 | 元素、化学式、筛选、分页、详情与重试；真实 HTTP/页面 |
| FR-003、FR-004、US2、SC-001 | 专属模型/路由/挂载删除 | T006–T008 | 旧接口不提供数据、无外部表依赖、部署配置验证 |
| FR-005、US2 | Overview、架构图和原型 | T009 | 引用、SVG 与原型检查 |
| FR-006、SC-003 | 真实证据工作流 + 按端点响应的测试替身 | T010–T011 | 保留原断言的全量回归 |
| FR-007、SC-004 | Spec、验证记录、Git、Issue | T001–T002、T012 | 文档门、实际通过证据与提交 |

## 实施顺序

1. 补齐并核对 Spec、Research、数据边界、契约、Checklist 与 Tasks。
2. 核对前轮代码清理，对真实查询与页面补充验收信号。
3. 基于已复现失败修正测试替身，完整重跑前端；Go 和相关 Python 验证。
4. 回写事实与验收结果，检查范围、自动提交，更新并关闭 #104。

## 复杂度与取舍

不增加退役兼容层或开关。不为旧数据执行迁移。不通过降低断言、跳过失败测试或改业务逻辑获得绿灯。限制测试并发作为可重复运行参数，无需修改生产配置。
