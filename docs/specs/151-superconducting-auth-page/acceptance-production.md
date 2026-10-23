# 正式落地验收（2026-10-23）

## 已实现

- /auth 独立于业务侧栏，侧栏及上传页入口统一跳转，成功后安全返回完整站内来源；无来源时普通登录 /news，新注册 /account。
- 已确认第四版视觉共用组件，保留无磁场线、减量白雾、点击加速、每秒一圈上限与定点停靠。正式页没有 Demo 提示、演示账号或固定验证码。
- 生产登录/注册/验证经现有 AuthContext；忘记密码经新增公开 Go 路由，真实邮箱随机码、一次性随机改密授权、bcrypt 更新及旧 JWT 撤销；无数据库迁移。
- Demo 仍可独立打开，仅 Demo 入口导入 mockAuth 和固定测试数据。旧 AuthDialog 已删除，展示和动画共享，避免复制维护。

## 验证证据

1. 六个 Vitest 文件共 62 项通过：auth-page（19）、auth-demo（12）、email-registration（5）、sidebar-navigation（7）、identity_ui（7）、language-switch（12）。覆盖来源安全、注册发信失败恢复、服务器重试时间、用户名、真实请求契约、改密和原 Demo 行为。
2. Go 相关处理器测试通过：TestPasswordReset、TestRegister、TestResend、TestVerify、TestPasswordChange 前缀；services/cache/middleware 独立包测试通过。找回测试包含未知/未验证/非活跃账号、注册/已登录改密码隔离、过期、五次失败、重发撤销、令牌与邮箱绑定、并发单次消费、数据库/缓存/邮件故障及会话版本失效。
3. 正式前端到真实 Go HTTP 处理器通过隔离端到端验证，结果见 [results.json](assets/production/results.json)。账号存入隔离 SQLite，Redis 协议由 miniredis 提供，邮件通过 Mailer 接口捕获随机验证码。实际验证前端没有 mockAuth，未拦截伪造认证响应；非认证页面依赖使用空数据夹具。
4. 邮件发送组件另通过本地 TLS/SMTP 测试（含 SendPasswordChangeCode 邮件内容）；上述浏览器全链路使用捕获邮件接口，不能冒称真实公网邮件已投递。
5. TypeScript 与前端正式构建通过；构建产物未包含 demo123456、researcher@example.com、unverified@example.com 或 createDemoAuth。既有 3Dmol eval 与较大分包告警不属于本功能。
6. 当前本机 8080 的新增 request 路由对格式非法邮箱返回 invalid_email，确认本地服务已加载新路由；没有在用户数据库创建测试账号或向实际用户邮箱发送测试邮件。
7. 正式页面截图和已批准 Demo 同尺寸并排核验：[对照](assets/production/comparison.png)、[桌面](assets/production/production-login-1440.png)、[窄屏](assets/production/production-login-320.png)、[验证码](assets/production/production-verify-email.png)、[找回密码](assets/production/production-reset-code.png)、[英文改密](assets/production/production-reset-en-390.png)。正式页移除演示信息属于预期；无侧栏、无竖线、图形样式保持。

## 本轮验证修正

初次浏览器测试的非认证空数据夹具不符合模型目录和上传任务列表的响应结构，导致 unrelated 的 find/map 页面错误；修正为各自预期结构后整条认证流程无页面异常。首张 /auth 截图误捕获 lazy 加载状态，已等待页面标题后重新捕获，未用加载画面冒充视觉验收。

## 当前限制与未关闭项

- Go 全量测试并非全通过：TestApplyPaperEvidenceArchivesManualReasonInReviewTransaction 在未修改的论文证据测试中报告 DELETE FROM scientific_evidence_checks SQL 预期未匹配。单独运行同样失败，与本次认证测试无依赖；未修改该模块，也未将全量结果标为通过。
- 公网邮箱真实收信、生产 MySQL 行锁并发行为与远端部署未验收；目前的隔离端到端不等同这些环境验收。
- 本次本地提交不推送；Issue 到远程 Spec 链接仍待验证，因此 Issue 保持开放。

共享组件迁移后，原 Demo 的 18 个布局状态、完整运动周期、点击加速/停靠与认证流程也重新通过，见 [Demo 回归记录](assets/production/demo-regression.json)。
