# 验收步骤

1. 打开包含图谱科学标题的上传解析草稿，在原标题后找到“图谱科学标题”，核对当前值、用途和字段键名。
2. 点击标签，确认打开对应来源核对；切到“字段设置”，当前值与主表单一致。该项不再出现在“待定位”区域。
3. 修改并立即保存，刷新核对保存值及原标题；确认修改后的值不沿用旧通过结论。
4. 对空值和缺失字段草稿重复打开，确认仍有空输入框且不自动复制原标题。
5. 只读、返修版本冲突、提交中时确认字段不可编辑；模拟保存失败，确认错误可见且不报告成功。
6. 桌面和 390px 窄屏重复检查，确认字段、标签和侧栏可操作。

自动验证：在 frontend 执行 `npm run test:upload-ui -- tests/01_decentralized_uploading/graph-title-form.test.tsx` 和 `npm run build`。浏览器脚本为 `tests/01_decentralized_uploading/graph-title-browser.mjs`，使用 PLAYWRIGHT_MODULE、CHROMIUM_PATH、FRONTEND_URL 和 GRAPH_TITLE_BROWSER_OUTPUT 指定本机运行路径。

浏览器 API 使用隔离草稿，不写用户数据；具体结果与存储层验证边界记录在 [validation.md](validation.md)。不因本地验证自动部署或推送。
