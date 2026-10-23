# Demo 验证记录

日期：2026-10-23。范围：Issue #154 的独立原型；不是正式页面或科学数据验收。

## 已执行

- npm run build 成功。
- Playwright 使用本机 Chrome 的隔离上下文，未使用用户登录会话。
- 1440×1100 桌面与 390×844 窄屏核验；页面水平宽度等于视口，点表可内部双向滚动，表头固定。
- 两类入口新开标签页，原页面输入保留，window.opener 为空。
- 原图覆盖/独立数据显示切换、279 点搜索和点选、无匹配提示与 CSV 实际下载通过。
- α²F 的无标定、参考失效、缺参考与零参考分支通过；DOS 分波显隐、模拟 HTTP 500 重试、空态通过。
- 使用已知解析积分的测试谱 α²F(ν)=ν、ν∈[1,2]，验证 λ=2 及对数均频 4/e THz，误差小于 10⁻⁶ THz。
- 浏览器 pageerror 为 0；/api/ 请求为 0。
- 首轮图像加载断言遇到加载竞态，修正为等待 decode 后再次完整通过。
- 视觉发现移动端坐标文字随固定画布缩小，改成响应式画布与固定字号，重新截图并复验通过。

## 证据

共用机器记录：[validation.json](../154-alpha2f-detail-demo/assets/validation.json)。
视觉记录：[design-qa.md](../154-alpha2f-detail-demo/demo/design-qa.md)。
核验脚本：../154-alpha2f-detail-demo/demo/scripts/validate-demo.cjs。
截图：../154-alpha2f-detail-demo/assets/ 下的 alpha/dos-desktop、mobile、overlay.png。

脚本运行前需提供安装了 playwright 的 NODE_PATH，使用本机 Chrome；地址默认 http://127.0.0.1:5194/，可由 SPECTRUM_DEMO_URL 覆盖。

## 未验证范围

正式 DOS 的 HTTP 500 未复现和修复；真实论文 α²F 幅值刻度及缩放未确认；合成积分不是材料真实结果。未连接业务 API、未部署、未修改正式谱、未推送。Issue 保持开放，正式 Spec 与 Demo 视觉认可仍待用户评审。
