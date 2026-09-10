# 实施计划：统一可收起侧栏

## 实现方式

`AppShell` 保留为唯一全局框架，使用两列网格，删除顶部 AppBar 行。侧栏 `sticky top: 0`、视口高度、独立滚动，正文 `minmax(0, 1fr)` 并移除框架 1440px 上限。底部组用自动上边距与最小空白分隔。

提取纯展示 `SidebarButton`，统一图标、标题、次级摘要、活动状态、折叠提示和可访问名称；不接管业务状态。复用已有 MUI 图标库。`LlmProviderSwitcher` 只调整入口呈现并接收 `collapsed`，弹窗与配置函数保持原实现。语言控件提取为 `LanguageSwitcher`，展开显示双语按钮，收起以语言图标打开选择菜单，两种形态仍调用同一 `setLang`。

角色按钮仍导航 `/account`，用户头像仍独立打开只有退出登录的菜单。`AuthProvider`、`RoleRoute`、`LazyRoutes` 和账号业务页面均继续使用当前实现。侧栏只改变样式，`Outlet` 固定在同一组件位置。

上传悬浮操作栏从 80px 改为 8px，预测卡片从 96px 改为 24px，均仅扣除原顶部栏 72px。其余页面内部尺寸独立于框架，不进行顺带重构。

## 需求映射

| 需求 / 故事 | 组件职责与事实来源 | 任务 | 验证 |
| --- | --- | --- | --- |
| FR-001–004 / US1、US2 | AppShell、SidebarButton、既有导航路由 | T001–T003 | 顺序、尺寸、浏览器滚动 |
| FR-005 / US3 | AuthProvider、RoleRoute、AccountPage、头像菜单 | T001、T003 | 三角色与访客、退出、深链 |
| FR-006 / US3 | LlmProviderSwitcher、LanguageContext、llmProvider | T001、T004 | 保存/清除、密钥、偏好、折叠菜单 |
| FR-007 / US2 | 固定 Outlet、UploadPage、TcPredictPage | T001、T005 | 输入与文件保持、悬浮操作 |
| FR-008 / 全故事 | 双语字典、MUI 按钮与提示 | T002–T004 | 键盘、名称、活动态 |
| SC-001–004 | 全部上述组件 | T006–T007 | 全量测试、生产构建、浏览器与文档 |

## 数据与接口影响

仅新增 AppShell 会话内折叠状态和语言菜单锚点，无后端实体或接口变化。UI 契约见 [contracts/sidebar.md](contracts/sidebar.md)，不新增数据模型文档。
