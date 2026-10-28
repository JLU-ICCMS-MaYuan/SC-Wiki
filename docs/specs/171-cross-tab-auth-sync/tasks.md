# 多标签页认证同步任务

输入：[规格](spec.md)、[计划](plan.md)、[研究](research.md)、[状态](data-model.md)、[契约](contracts/auth-sync.md)。

## 准备与基础

- [x] T001 在 tests/02_identity_governance/auth-sync.test.tsx 建立跨页状态、迟到响应与网络错误失败测试。
- [x] T002 在 frontend/src/context/AuthContext.tsx 统一当前会话快照和世代保护。

## US1、US2：登录与退出同步（P1）

独立验收：一次登录与一次退出均覆盖五页。

- [x] T003 在 frontend/src/context/AuthContext.tsx 接入共享存储事件、统一登录/验证/退出与身份核验去重。

## US3：后台恢复与迟到响应（P1）

独立验收：恢复后台页；旧成功、401、网络失败均不破坏新会话。

- [x] T004 在 frontend/src/context/AuthContext.tsx 完成恢复监听、旧响应隔离及资料更新保护。

## 跨故事导航与验收

- [x] T005 在 frontend/src/pages/AuthPage.tsx 实现外部登录安全回跳，并补充 tests/02_identity_governance/auth-page.test.tsx 回归。
- [x] T006 在 tests/02_identity_governance/auth-cross-tab-browser.mjs 验证五页十轮、真实请求身份、后台恢复、旧响应、页面位置/编辑保护；运行组件测试与构建，记录 validation.md。
- [x] T007 使用 Overview Skill 更新 docs/overview/06_Researcher_Community_Forum/registration-login-and-jwt.md，回写 Issue 与检查表并只提交本次文件。

## 执行依赖

T001 → T002 → T003 → T004 → T005 → T006 → T007。同一认证文件修改串行，不启用多代理并行。
GitHub Issue 是未完成行动的状态来源，本文件仅记录技术拆解。

## 需求覆盖

FR-001/FR-005：T001～T003、T006；FR-002：T001、T003、T006；FR-003/FR-004：T001、T004、T006；FR-006：T003、T006；FR-007：T005、T006。
SC-001～SC-004 均由 T006 汇总证据。

## 交付顺序

先验证正常登录与退出，再加入竞态和恢复，最后整体回归；不以单元测试替代浏览器原生跨页事件验收。


## 验证依据

T001～T006 对应 [验收记录](validation.md) 与 [机器结果](validation.json)；T007 回写认证 Overview 与 Issue 的本地文档路径，远程链接仍待授权推送后核验。保存相关测试补齐了现有 PATCH 接口替身，仅暂存本次两处修改。
