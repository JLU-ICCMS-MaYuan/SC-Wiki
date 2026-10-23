# 演示任务与正式集成边界

输入：[spec.md](spec.md)、[plan.md](plan.md)、[research.md](research.md)、[界面契约](contracts/ui.md)。

- [x] T001 归档原图与原始需求：`docs/specs/152-account-center-demo/assets/`、`spec.md`。
- [x] T002 [US1] 在 `prototypes/account-center/src/App.jsx` 完成资料查看与编辑，并验证 FR-001/002、SC-001/002。
- [x] T003 [US2] 在同文件完成收录／检查贡献与筛选，验证 FR-003/005、SC-003。
- [x] T004 [US3] 在同文件完成工作入口与独立目标模块，验证 FR-004、SC-003。
- [x] T005 运行原型构建、浏览器主流程与视觉比对，形成 `prototypes/account-center/design-qa.md`，验证 FR-006、SC-004。
- [x] T006 用户在两轮 demo 后要求“开始实现”，启动正式接入，最新基线见 Spec/Plan。

## 正式接入

- [x] T008 更新正式实施基线、Plan、Research 和接口契约。
- [x] T009 真实邮箱验证码改密、会话撤销及负向回归。
- [x] T010 本人真实检查贡献查询、归属与去重测试。
- [x] T011 三角色账户布局、只读编辑、贡献列表与管理模块深链。
- [x] T012 前后端及浏览器验证，Overview、Issue 和验收事实回写，限定范围提交。

T001 → T002 → T003 → T004 → T005；T006 依赖用户反馈。本清单只跟踪技术拆解，协作状态以 Issue #152 为准。

T002–T005 的原型验收证据：`prototypes/account-center/design-qa.md` 与 `scripts/verify-browser.mjs`；生产实现不在本清单完成项中。

- [x] T007 [US4] 在 `prototypes/account-center/src/App.jsx` 扩展两步邮箱验证码改密，`src/styles.css` 增加局部布局，新增浏览器回归验证 SC-005；同步 Spec 与 Issue #152。证据：`scripts/verify-password.mjs`，仅原型验收。

正式接入证据：acceptance.md、production-design-qa.md、Go 专项／全包排除已知基线失败后的结果、28 项相关前端测试与 2 项英文测试。浏览器接口为隔离响应，外部邮箱投递未实测；不将已知失败或未验证项计作通过。
