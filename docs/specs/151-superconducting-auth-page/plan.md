# 实施计划：独立登录注册页与超导悬浮动画

**Issue**：[#151](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/151) · **日期**：2026-10-22 · **Spec**：[spec.md](spec.md)

## 摘要与技术上下文

React 19 / TypeScript 5.6 / MUI 7 / Vite 5，复用主题与 LanguageProvider。独立 HTML 入口加载 Demo，不引入生产 App 或 AuthProvider。SVG 与 requestAnimationFrame 驱动默认 12 秒一周、点击可变速并定点停靠的动画，直接更新 SVG 变换，不让每帧触发表单重渲染。目标为桌面及移动浏览器，后台无持续动画帧。无新增依赖、后端或持久化数据；Vitest/jsdom 验证行为，浏览器验证布局与动画。

## 质量门

| 来源 | 要求 | 满足方式 | 状态 |
| --- | --- | --- | --- |
| 用户批准方案 | Demo 通过评审后才正式接入 | 独立 HTML，生产路由与认证调用不动 | 第一阶段设计通过 |
| 用户 SVG 选择 | 允许直接代码绘制科学插画 | 无图片生成依赖，不伪称已做效果图复刻 | 通过 |
| AGENTS.md | mayuan、显式路径提交、不推送 | 写入前查分支，完成后局部提交 | 执行时复核 |
| Spec | 原文、原图与分阶段验收 | 原文续篇、原图哈希与 FR/SC 映射 | 见 requirements.md |
| Issue 关闭门 | 远程链接与正式功能验收 | 本地链接注明待验证，保持 Issue 开放 | 待第二阶段 |

## 文档与代码结构

本目录保存 spec、approved-request、plan、research、data-model、contracts/demo-auth、tasks、quickstart、design-qa、checklists/requirements 和原始截图。

- `frontend/auth-demo.html`：独立预览入口，不加入生产 Vite 构建入口。
- `frontend/src/demos/auth/`：页面、样式、动画、演示认证服务及双语文案。
- `tests/02_identity_governance/auth-demo.test.tsx`：模拟认证、隔离和表单行为。

页面编排、动画、模拟服务各负一责；复用用户名校验，避免拷贝生产认证逻辑。原有 AuthDialog、AppShell、UploadPage、AuthContext 均不改动。

## 需求到设计与任务映射

| 来源 | 设计与数据来源 | 任务 | 验证 |
| --- | --- | --- | --- |
| FR-001、SC-004、US1 | 独立入口；入口预览用 `?view=entry`，两个演示入口均进入此 Demo | T003、T005 | HTTP、构建、浏览器导航 |
| FR-002、FR-007、SC-001 | 60/40 布局、主题、LanguageProvider、双语字典 | T005、T007 | 多尺寸、双语、键盘 |
| FR-003、FR-004、FR-008、SC-002 | SVG 场景、动画时钟、媒体查询及可见性事件 | T004、T007 | 完整周期、暂停、后台与减少动画 |
| FR-005、FR-006、SC-003、US2 | 内存服务与既有 usernameValidationError | T002、T003、T005、T006 | 流程测试与零 API 请求 |
| FR-009、SC-005、US3 | 正式 /auth 与既有 AuthContext；当前不实施 | T009、T010 | 正式集成与文档门 |

## 阶段与依赖

文档 → 独立入口与服务 → 动画与表单 → 测试、视觉检查及 Demo 提交 → 用户评审 → 正式集成。第一阶段只到 T008。第一阶段完成不等于 Feature 完成。

## 复杂度说明

独立入口避免误改现有工作流；模拟服务专门演示失败和恢复而不触碰真实账号。无需新建应用脚手架、添加 WebGL 库或抽象生产认证适配框架。

## 2026-10-23 修改实施

新增 orbitMotion.ts 作为纯运动状态模型，scene 用 SVG 坐标逆变换得到点击角度，按角位移检测跨过目标并精确停靠。复用同一可暂停动画时钟驱动白雾，不新增 3D 依赖；细化陶瓷颗粒、霜晶、切边、环槽和高光。去掉 CSS 竖线。

密码找回使用独立 PasswordReset 组件，由登录页按钮进入；mockAuth 增加请求重置码、验证、凭证消费和改密。邮箱重置挑战与注册挑战分开，不伪装生产服务。双语文案、自动化流程和视觉证据一起更新。

FR-010～012 / SC-006 → orbitMotion + SuperconductorScene + CSS → T011/T013；FR-013 / SC-007 → PasswordReset + mockAuth → T012/T013。正式密码重置 API 与 SMTP 仍需第二阶段设计和实现。
