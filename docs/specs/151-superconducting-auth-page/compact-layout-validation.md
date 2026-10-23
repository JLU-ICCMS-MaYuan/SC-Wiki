# 登录注册页紧凑布局验收

## 原问题与原因

两张用户截图及元数据见 [来源记录](assets/compact-layout/sources.json)。重新打开本机正式 /auth，在 1440×760 CSS 视口测得登录内容约 879px、注册约 1031px；1920×840 同样分别约 891px、1031px。问题是原 108px 页头、68px 页脚、动画/标题较高以及表单内部多层留白共同撑高内容，非单独滚动条样式问题。

## 修改

只调整认证页共享 CSS：页头从 108px 改为常规 72px、短桌面 60px；减少头尾与主区域、表单标题/字段间隔，输入框常规 44px、短桌面 42px；主操作保持至少 44px。动画高度随可用视口收缩，保留构图与交互。手机也减小部分留白。

不使用 overflow:hidden、不设置裁剪式固定高度、不通过 transform 缩小全页。手机、极短窗口、展开说明或长错误内容保留自然滚动。只修改 CSS，不改认证、数据或运动速度逻辑。

## 浏览器结果

- 5 个桌面视口 × 中英文 × 登录/注册 = 20 个组合全部通过。1920×840、1440×760、1366×650、1280×720、1024×768 的 scrollHeight 均等于视口高度，提交按钮完整在视口内。
- 1366×650 下运行动画 14 秒，覆盖完整一圈，7 个采样点都没有产生横向或纵向溢出。
- 忘记密码邮箱步骤在 1366×650 完整可见。
- 390×844、320×720 手机与 1024×480 极短桌面，在注册错误和展开说明状态下仍无横向溢出；Tab 可聚焦提交按钮并由浏览器滚入视口。
- 测试未发送任何 API 请求，无页面异常。共享 CSS 的独立 Vite 构建通过。
- 此次未重新验证邮件发送或修改密码，未修改这些业务流程；不宣称任意缩放/屏幕尺寸都永远不需要滚动。

## 视觉复查

已查看桌面登录、桌面注册、英文短桌面及同尺寸修改前后合成对照。整体白底、品牌配色、右侧表单和圆片材质保留；标题和动画适度缩小，字段间距更紧凑，主要按钮和帮助文字没有遮挡。长内容和极短视口允许滚动属于可访问性兜底，不是假装无溢出。

证据：[修改前测量](assets/compact-layout/before-metrics.json)、[修改后测量](assets/compact-layout/results.json)、[前后对照](assets/compact-layout/comparison.png)、[中文注册](assets/compact-layout/zh-register-1440.png)、[英文短桌面](assets/compact-layout/en-register-1366.png)、[极窄屏错误态](assets/compact-layout/register-error-320x720.png)。

复现：使用 Playwright 运行 tests/02_identity_governance/auth-layout-browser.mjs，可用 PLAYWRIGHT_MODULE、CHROMIUM_PATH、FRONTEND_URL、ARTIFACT_DIR 指定环境；本次使用已授权的本机无头 Chrome、新建浏览器上下文。未进行部署、重启、迁移或推送。
