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

- [x] T009 [US3] 经明确批准后在 frontend/src/App.tsx、components/AppShell.tsx、pages/UploadPage.tsx 接入独立 /auth 与统一入口，复用真实认证及合法站内回跳。
- [ ] T010 [US3] 验证正式认证，更新 docs/overview/README.md 与 docs/overview/06_Researcher_Community_Forum/registration-login-and-jwt.md，核验远程 Spec 后处理 Issue 关闭门。

## 依赖、覆盖与独立验收

T001 → T002 → T003 → T004/T005 → T006/T007 → T008 → 用户视觉评审 → T009 → T010。同文件串行；本次不委派并行代理。

- US1：打开独立入口、查看多尺寸页面、完整绕行和暂停；覆盖 FR-001～004、FR-007～008、SC-001～002/004。
- US2：模拟成功/失败/验证/重发且没有真实请求；覆盖 FR-005～006、SC-003～004。
- US3：真实入口、认证与回跳；覆盖 FR-009、SC-005，当前未实施。

MVP 是 US1+US2。勾选 Demo 任务只代表 Demo 行为，不代表生产集成。

## 第一阶段证据

T001：原文、两张原图、Issue #151 及 FR/SC 映射齐备；T002/T003/T005/T006：6 项 Vitest 与浏览器认证流程通过；T004/T007：完整周期、暂停及多尺寸截图见 design-qa.md 和 assets/browser-results.json；T008：quickstart.md 与本地预览可用，本次源码提交可由 `git log -- frontend/auth-demo.html` 复查。T009/T010 保持未完成，等待用户 Demo 评审。

## 2026-10-23：用户视觉评审修改

- [x] T011 [US1] 在 frontend/src/demos/auth/orbitMotion.ts、SuperconductorScene.tsx、auth-demo.css 实现无竖线、材质/白雾、点击加速、上限和轨道定点停靠；覆盖 FR-010～012。
- [x] T012 [US2] 在 frontend/src/demos/auth/PasswordReset.tsx、AuthDemo.tsx、mockAuth.ts、copy.ts 实现从忘记密码按钮进入的邮箱验证改密模拟流程；覆盖 FR-013。
- [x] T013 [US1] 扩展 tests/02_identity_governance/auth-demo.test.tsx 与 auth-demo-browser.mjs，记录 SC-006/007 验证及新截图，更新本目录验收记录。

T011/T012 完成后执行 T013；正式 T009/T010 仍待用户批准。

- [x] T014 [US3] 正式接入获批后，在 docs/specs/151-superconducting-auth-page/contracts/ 确认真实找回密码契约，结合届时 goserver/handlers/auth.go、邮件服务及 frontend/src/context/AuthContext.tsx 完成发信、验证码、安全改密和真实验收；不得直接发布 Demo 服务。

第二版证据：T011/T013 见 assets/revision-2/results.json 的 speedCap、stopCoordinates、trackStopRestart、vapor；T012/T013 见 12 项 Vitest 及浏览器找回全流程。T014 属于未来正式阶段，不在本次 Demo 授权中。

## 第三版：速度、抗磁性和浓雾

- [x] T015 [US1] 在 frontend/src/demos/auth/orbitMotion.ts 将上限改为每秒一圈，并扩展 tests/02_identity_governance/auth-demo-browser.mjs 的最高速周期和高速停靠验证。
- [x] T016 [US1] 在 frontend/src/demos/auth/MagneticField.tsx、SuperconductorScene.tsx、copy.ts、auth-demo.css 实现绕体场线、屏蔽电流图例及视频参考的分层浓雾；在本目录 research.md 保存论文和视频依据。
- [x] T017 [US1] 在 docs/specs/151-superconducting-auth-page/assets/revision-3/ 保存源视频记录、裁剪帧、截图及验证结果，更新 quickstart.md、design-qa.md 与 Issue #151。

第三版证据：T015 见 revision-3/results.json 的 measuredMaxSpeedPeriodMs（约 999.29ms）与 stopCoordinates；T016/T017 见 research.md、视频来源 JSON、参考帧/实现并排图及 design-qa.md。正式阶段 T009/T010/T014 保持未完成。

## 第四版：精简视觉

- [x] T018 [US1] 删除 frontend/src/demos/auth/MagneticField.tsx 与相关展示/样式，将 SuperconductorScene.tsx 雾量减半，更新 copy.ts、浏览器断言和本目录证据；覆盖 FR-017/018、SC-010。

## 正式实施（用户已授权）

- [x] T019 [US3] 在 frontend/src/features/auth/、pages/AuthPage.tsx、lib/authNavigation.ts 提取共享界面和真实服务，接入 App.tsx、AppShell.tsx、UploadPage.tsx 的统一登录入口与安全来源回跳。
- [x] T020 [US3] 在 goserver/handlers/password_reset.go、goserver/main.go 实现公开邮箱验证码找回，补充处理器及验证码隔离/过期/并发测试。
- [x] T021 [US3] 在 tests/02_identity_governance/ 完成正式路由/服务测试与隔离端到端验证，更新 Overview、当前契约及验收记录，提交本次文件并同步 Issue。

## 正式阶段证据与剩余门槛

T009/T019：生产 /auth、两个入口、站内来源校验及注册/登录端到端通过。T014/T020：Go 公开找回路由及隔离/过期/并发/错误测试通过，邮件组件 TLS/SMTP 测试通过。T021：62 项前端测试、正式构建、隔离真实 HTTP 浏览器与 Overview 更新完成，具体证据见 acceptance-production.md。

T010 保持未完成：Overview 已更新，但公网投递、目标 MySQL 环境验收和远程 Spec 链接仍未完成，不以本地文件存在关闭 Issue。

## 注册字段命名与防重

- [x] T022 [US3] 修改 frontend/src/features/auth/copy.ts 注册标签；更新标签选择器并核验失焦/提交/数据库防重，将结果和截图保存到 assets/username-label/，同步 Issue 与 Overview。

T022 证据：username-label-validation.md；37 项前端、3 项 Go 目标测试、TypeScript 与正式页面双语核验通过；本机 MySQL 唯一索引只读检查及重复组计数已记录。

## 紧凑布局

- [x] T023 [US3] 在 frontend/src/features/auth/auth-demo.css 压缩头尾、动画和表单留白；新增 tests/02_identity_governance/auth-layout-browser.mjs 验证桌面双语登录/注册无纵向溢出及短屏/手机内容可达；保存本 Spec 证据并同步 Issue。

T023 证据：compact-layout-validation.md、assets/compact-layout/results.json；20 个桌面组合、短屏键盘访问、完整动画绕行及共享样式打包通过。
