# 多标签页认证同步实施计划

**Issue**：[ #171 ](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/171)
**日期**：2026-10-28
**规格**：[spec.md](spec.md)

## 摘要

统一 AuthContext 同步入口，监听共享存储与页面恢复，使用会话世代和请求代次隔离旧响应；AuthPage 响应外部认证。

## 技术上下文

- TypeScript ~5.6、React ^19.2、React Router ^6.28、Vite ^5.4。
- 保留 localStorage 凭据/用户存储与 Go 认证接口，新增无敏感信息世代标记。
- Vitest/jsdom 组件测试；Playwright 五页及隔离 Go HTTP 夹具。
- 同源桌面浏览器，五页十轮；SC-002 两秒，服务响应耗时单列。
- 不新增依赖、数据库迁移、部署或 Git 推送；保持 mayuan 分支。

## 质量门

| 来源 | 要求 | 处理 |
| --- | --- | --- |
| AGENTS.md | 保留其他任务修改、只提交本次文件 | 显式路径暂存并审查 |
| 已确认 Spec | 不刷新业务页、不放宽权限 | 认证层局部更新，服务器权限不变 |
| Spec Skill | 完整原话、确认、可追踪 | Spec 与检查表记录 |
| Issue Skill | 远程文档链接 | 仅登记本地路径，待授权推送后核验；不关闭 Issue |

单项需求已确认，可进入实现；远程链接不冒充通过，最终关闭门保留。

## 产物

spec.md、plan.md、research.md、data-model.md、contracts/auth-sync.md、quickstart.md、tasks.md、checklists/requirements.md；验收后另记 validation.md。

## 代码触点

- frontend/src/context/AuthContext.tsx：同步、核验、世代、旧响应保护。
- frontend/src/pages/AuthPage.tsx：外部登录回跳。
- tests/02_identity_governance/auth-sync.test.tsx：状态与竞态测试。
- tests/02_identity_governance/auth-cross-tab-browser.mjs：真实五页认证。
- docs/overview/06_Researcher_Community_Forum/registration-login-and-jwt.md：已实现行为回写。

## 需求映射

| 来源 | 设计 | 任务与验证 |
| --- | --- | --- |
| FR-001、FR-005 / US1 / SC-001、SC-002 | 统一认证视图、storage 与真实身份核验 | T001～T003、T006；五页十轮与 API 身份 |
| FR-002 / US2 / SC-001 | 退出更新世代、清共享凭据 | T001、T003、T006 |
| FR-003 / US3 / SC-002 | focus/visibilitychange 补漏 | T004、T006 |
| FR-004 / US3 / SC-003 | 会话世代、请求代次、资料更新保护 | T001、T004、T006 |
| FR-006 / SC-004 | 局部状态更新，不整页刷新 | T003、T006 |
| FR-007 / SC-004 | 外部登录回跳与本地提交区分 | T005、T006 |

## 阶段与依赖

先建立完整文档与失败测试，再实现共享状态；随后补充后台恢复、竞态与导航；最后执行浏览器、构建与文档验收。

## 必要复杂度

世代标记用于区分相同 JWT 的两次会话；单纯 token 比较不能排除同秒重新登录时的旧响应。保留现有凭据键以兼容 UploadPage 等消费者。
