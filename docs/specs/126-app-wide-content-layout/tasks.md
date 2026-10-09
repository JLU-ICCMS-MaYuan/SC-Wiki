# 实施任务：全站页面主体窄边距布局

**输入**：[spec.md](spec.md)、[plan.md](plan.md)、[research.md](research.md)、[contracts/layout.md](contracts/layout.md)

## 阶段 1：准备与旧约定收敛

- [x] T001 核对 `frontend/src/components/AppShell.tsx`、各页面根容器与 `docs/specs/124-upload-parsing-layout/` 的布局现状。
- [x] T002 修订 `docs/specs/124-upload-parsing-layout/` 及 Issue #124 的收起后边距约定，保持新旧需求一致。

## 阶段 2：用户故事 1——全站 8px 页面主体（P1）

**独立验收**：各类路由和侧栏状态均测得约 8px 左右间隙。

- [x] T003 [US1] 在 `frontend/src/components/AppShell.tsx` 统一水平 8px 且维持原竖向间距。
- [x] T004 [US1] 移除 `frontend/src/pages/UploadPage.tsx` 的展开态负边距并验证 #124 常驻栏。
- [x] T005 [US1] 清除账户、公开主页、社区讨论/系统、管理工作台、管理员论文编辑页面根容器的最大宽度；清除 `frontend/src/pages/KnowledgeGraphPage.tsx` 的额外水平外层内边距。

## 阶段 3：用户故事 2——窄窗口可操作（P1）

**独立验收**：375px 与 768px 不新增页面级横向滚动，控件保持可用。

- [x] T006 [US2] 将 `frontend/src/pages/TcPredictPage.tsx` 与 `frontend/src/pages/AdminPaperEditPage.tsx` 的固定多列工作区改为窄屏响应式布局。
- [x] T007 [US2] 在 `frontend/src/components/AppShell.tsx` 对 `/rag` 的直属根容器覆盖横向负边距，保留竖向全高补偿；不纳入 `frontend/src/pages/RagPage.tsx` 的同期业务改动。

## 阶段 4：验证与文档

- [x] T008 按 `docs/specs/126-app-wide-content-layout/quickstart.md` 运行定向回归、生产构建及浏览器视口验收。
- [x] T009 在行为落地后更新 `docs/overview/README.md` 与上传功能 Overview，并同步 Issue #126 的验收与 Documentation Impact。

## 依赖与执行顺序

- T002 先解决 #124 与新规则的冲突；T003 后实施 T004、T005；T006、T007 完成后执行 T008、T009。
- RAG 工作树不可安全分离，不得把其他任务改动纳入本任务提交；壳层中的路由限定规则须通过真实视口几何核验。

## 需求覆盖

| 来源 | 任务 | 验证 |
|------|------|------|
| FR-001、FR-002、SC-001 / US1 | T003、T005、T008 | 跨路由左右边距和整页宽度 |
| FR-003、FR-005、SC-003 / US1 | T002、T004、T008 | 上传收起/展开与常驻栏 |
| FR-004、SC-002 / US2 | T006、T007、T008 | 窄屏无页面溢出 |
| FR-006、SC-004 / US1 | T005、T008、T009 | 局部宽度与回归 |
