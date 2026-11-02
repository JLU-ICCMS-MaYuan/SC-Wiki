# 实施计划：搜索作为默认首页

**Issue**：[功能 #202](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/202)

**日期**：2026-11-02；**规格**：[spec.md](spec.md)

## 摘要与技术上下文

React 19、TypeScript 5.6、React Router 6、MUI 7、Vite 5。仅调整前端路由与导航，无新依赖、数据库、接口或持久化键。目标为桌面及移动浏览器；沿用现有按需加载策略，不增加页面跳转或首屏业务请求。

## 质量门

| 来源 | 要求 | 实现方式 | 设计检查 |
| --- | --- | --- | --- |
| 用户原话 | 交换热点和搜索，直接进入搜索 | 根入口及侧栏交换 | 通过 |
| #101 | 折叠不卸载正文，角色和语言一致 | 保留 AppShell 结构，仅调顺序与退出目的地 | 通过 |
| #151 | 合法来源优先，注册默认用户中心 | 只替换无来源 `/news` 回退 | 通过 |
| #178、#174 | 输入及 URL 契约不回退 | 不修改 SearchPage 或编辑组件 | 通过 |
| AGENTS.md | mayuan、精确提交、不推送 | 每次写入前核对，保留已有删除与未跟踪目录 | 执行时核验 |

## 文档与源码结构

本目录提供 spec、plan、research、quickstart、tasks 和 checklists/requirements；不创建数据模型及接口 contracts，因为没有数据或 API 变更。

- `frontend/src/App.tsx`：首屏 SearchPage 直接惰性加载，根路径跳转 `/search`。
- `frontend/src/LazyRoutes.tsx`：热点移入其他页面路由，删除重复搜索路由。
- `frontend/src/components/AppShell.tsx`：交换导航项，退出进入搜索。
- `frontend/src/pages/AuthPage.tsx`、`HomePage.tsx`：更新默认出口。
- `tests/02_identity_governance/sidebar-navigation.test.tsx`、`auth-page.test.tsx`：调整既有行为期望；跨标签页浏览器脚本同步默认回退期望。
- `docs/overview/README.md`：只同步已验证的当前事实。

## 需求到设计和验证映射

| 来源 | 设计决策与职责 | 任务 | 验证 |
| --- | --- | --- | --- |
| FR-001 / SC-001 | App 根路由、HomePage；品牌沿用 `/` | T002 | 真实浏览器根入口与品牌往返 |
| FR-002 / SC-001 | AppShell 单一导航列表 | T003 | 既有侧栏完整宿主与桌面/手机浏览器 |
| FR-003 / SC-002 | AuthPage 来源安全逻辑保留；AppShell 退出 | T003、T004 | 认证回归及角色退出检查 |
| FR-004 / SC-002 | 首屏路由归 App，其余归 LazyRoutes | T002、T005 | 检索既有回归、真实页面与模块请求 |
| SC-003 | 当前事实归 Overview | T005、T006 | 构建及文档链接检查 |

## 阶段与依赖

先完成文档门 T001，再串行调整路由、导航、认证出口，之后运行既有回归和隔离浏览器验收，最后同步 Overview、证据及本地提交。无须并行代理。MVP 即整个单用户故事；不引入路由常量层或额外状态。
