# 演示任务与正式集成边界

输入：[spec.md](spec.md)、[plan.md](plan.md)、[research.md](research.md)、[界面契约](contracts/ui.md)。

- [x] T001 归档原图与原始需求：`docs/specs/152-account-center-demo/assets/`、`spec.md`。
- [x] T002 [US1] 在 `prototypes/account-center/src/App.jsx` 完成资料查看与编辑，并验证 FR-001/002、SC-001/002。
- [x] T003 [US2] 在同文件完成收录／检查贡献与筛选，验证 FR-003/005、SC-003。
- [x] T004 [US3] 在同文件完成工作入口与独立目标模块，验证 FR-004、SC-003。
- [x] T005 运行原型构建、浏览器主流程与视觉比对，形成 `prototypes/account-center/design-qa.md`，验证 FR-006、SC-004。
- [ ] T006 用户评审 demo 后，再确认正式集成的具体视觉、接口、检查贡献来源及授权边界。

T001 → T002 → T003 → T004 → T005；T006 依赖用户反馈。本清单只跟踪技术拆解，协作状态以 Issue #152 为准。

T002–T005 的原型验收证据：`prototypes/account-center/design-qa.md` 与 `scripts/verify-browser.mjs`；生产实现不在本清单完成项中。
