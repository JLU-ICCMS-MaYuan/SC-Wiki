# 实施任务：搜索作为默认首页

输入：[规格](spec.md)、[计划](plan.md)、[研究](research.md)。数据模型及接口文件不适用。

## 阶段 1：准备与基础

- [x] T001 对照原话及 #101/#151/#178 检查当前路由和数据所有权，在 `docs/specs/202-search-default-home/` 完成规格与设计。依据：plan 的需求覆盖表及 research 的代码依据；用户已直接授权创建与实施。

## 阶段 2：用户故事 1——进入网站即开始检索（P1，MVP）

- [x] T002 [US1] 在 `frontend/src/App.tsx`、`frontend/src/LazyRoutes.tsx` 和 `frontend/src/pages/HomePage.tsx` 调整首屏与遗留默认入口。证据：生产构建浏览器根入口及首屏模块检查通过，见 validation.md。
- [x] T003 [US1] 在 `frontend/src/components/AppShell.tsx` 交换前两项，并在 `frontend/src/pages/AuthPage.tsx` 同步默认首页出口。证据：既有侧栏宿主及认证回归、桌面/手机往返和登录/退出检查通过。
- [x] T004 [US1] 同步 `tests/02_identity_governance/sidebar-navigation.test.tsx`、`auth-page.test.tsx` 和 `auth-cross-tab-browser.mjs` 中既有入口契约。证据：受影响 Vitest 通过，浏览器脚本语法检查通过；未重跑该脚本的真实 Go 夹具全流程，详见 validation.md 限制。

## 阶段 3：验证与收尾

- [x] T005 运行相关既有回归、生产构建和隔离浏览器入口验收，记录在 `docs/specs/202-search-default-home/validation.md`。证据：7 个文件 67 项测试、TypeScript/Vite 构建、13 个浏览器场景组通过，assets/verification.json 保留源码哈希。
- [x] T006 根据已验证实现更新 `docs/overview/README.md` 及对应检索/认证说明，检查文档与任务覆盖和本次提交范围。证据：三处 Overview 与实际路由一致；10 个 Markdown 的本地相对链接检查通过，原有删除及未跟踪目录排除。Git 提交按仓库自动提交规则执行。

## 依赖、覆盖与交付

T001 → T002 → T003 → T004 → T005 → T006；同一导航链路串行处理，无需代理或并行实现。只有一个故事，完整实现即 MVP。

| 来源 | 任务 | 独立验收 |
| --- | --- | --- |
| FR-001 | T002、T005 | 根入口与品牌实际到搜索 |
| FR-002 | T003、T004、T005 | 顺序、折叠、语言和角色 |
| FR-003 | T003、T004、T005 | 来源保留与默认回退 |
| FR-004 | T002、T005 | 检索/热点直达、结果 URL |
| SC-001/002/003 | T005、T006 | 浏览器、既有回归、构建及 Overview |
