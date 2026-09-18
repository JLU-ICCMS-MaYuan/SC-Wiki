# 技术研究与取舍

- 框架集中于 `AppShell`，全部页面通过 `Outlet` 加载，因此一次调整即可覆盖三角色与访客，避免复制布局（DRY、单一职责）。
- 七个导航路由、角色 `/account`、工作台跳转和权限来源已在 `App.tsx`、`LazyRoutes.tsx`、`RoleRoute.tsx`、`AccountPage.tsx` 与历史 #40/#43/#44 核对。角色按钮不直接改跳工作台，避免丢失个人中心。
- #48 的滚动可达性仍需满足；移除顶栏后导航偏移归零，同时扣除上传、预测悬浮项原 72px 顶栏高度。
- #73 的模型切换已封装保存、连接测试与密钥显示；复用组件而不复制弹窗。#74 的 `LanguageContext` 继续拥有字典、偏好与 `html lang`。
- 复用 MUI 已安装图标，无新依赖。共享小型展示按钮而不引入导航框架（KISS、YAGNI）。
- 使用 CSS 网格与 sticky，不添加滚动监听或以主内容 remount 实现宽度切换；窄屏默认图标栏，保留主动展开。
- 根 README 含禁止 AI 直接编辑的约束，实际导航使用说明增量同步到 Overview 和 quickstart。
