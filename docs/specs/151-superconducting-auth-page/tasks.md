# 实施任务：独立登录页

输入：[Spec](spec.md)、[Plan](plan.md)、[Research](research.md)、[状态](data-model.md)、[契约](contracts/demo-auth.md)。

## 准备与基础

- [x] T001 在 docs/specs/151-superconducting-auth-page/ 保存已批准需求、截图与设计、映射，并关联 Issue #151。
- [x] T002 在 tests/02_identity_governance/auth-demo.test.tsx 添加隔离服务与流程行为测试。
- [x] T003 在 frontend/auth-demo.html 与 frontend/src/demos/auth/mockAuth.ts 建立独立入口及内存认证服务。

## US1：视觉预览（P1）

- [x] T004 [US1] 在 frontend/src/demos/auth/SuperconductorScene.tsx 实现轨道、悬浮圆片、阴影及受控动画。
- [x] T005 [US1] 在 frontend/src/demos/auth/AuthDemo.tsx、auth-demo.css、copy.ts、main.tsx 实现分栏、表单、双语与入口预览。

## US2：交互与验证（P1）

- [x] T006 [US2] 运行 tests/02_identity_governance/auth-demo.test.tsx，验证模拟认证、表单与无真实请求。
- [x] T007 [US1] 在 docs/specs/151-superconducting-auth-page/design-qa.md 记录多尺寸、双语与动画验证证据，完成构建。
- [x] T008 [US2] 在 docs/specs/151-superconducting-auth-page/quickstart.md 记录预览和演示步骤，提交本次文件，交付 Demo 等待视觉评审。

## US3：正式集成（P2，用户评审通过后才开始）

- [ ] T009 [US3] 经明确批准后在 frontend/src/App.tsx、components/AppShell.tsx、pages/UploadPage.tsx 接入独立 /auth 与统一入口，复用真实认证及合法站内回跳。
- [ ] T010 [US3] 验证正式认证，更新 docs/overview/README.md 与 docs/overview/06_Researcher_Community_Forum/registration-login-and-jwt.md，核验远程 Spec 后处理 Issue 关闭门。

## 依赖、覆盖与独立验收

T001 → T002 → T003 → T004/T005 → T006/T007 → T008 → 用户视觉评审 → T009 → T010。同文件串行；本次不委派并行代理。

- US1：打开独立入口、查看多尺寸页面、完整绕行和暂停；覆盖 FR-001～004、FR-007～008、SC-001～002/004。
- US2：模拟成功/失败/验证/重发且没有真实请求；覆盖 FR-005～006、SC-003～004。
- US3：真实入口、认证与回跳；覆盖 FR-009、SC-005，当前未实施。

MVP 是 US1+US2。勾选 Demo 任务只代表 Demo 行为，不代表生产集成。

## 第一阶段证据

T001：原文、两张原图、Issue #151 及 FR/SC 映射齐备；T002/T003/T005/T006：6 项 Vitest 与浏览器认证流程通过；T004/T007：完整周期、暂停及多尺寸截图见 design-qa.md 和 assets/browser-results.json；T008：quickstart.md 与本地预览可用，本次源码提交可由 `git log -- frontend/auth-demo.html` 复查。T009/T010 保持未完成，等待用户 Demo 评审。
