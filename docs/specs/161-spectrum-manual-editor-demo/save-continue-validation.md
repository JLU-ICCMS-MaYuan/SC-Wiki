# 保存并继续编辑验收

日期：2026-10-27，Asia/Shanghai。关联[#161](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/161)。

## 根因与实现

原save()无条件调用onClose，切换元素和离开编辑器复用该流程，保存会提前关闭编辑器。父页面原本不推进editorInput的版本，因为保存后必定关闭。

本轮用明确close/switch意图区分行为。切换时主操作为“保存并继续编辑”，成功后留在编辑器并加载目标元素；取消为“留在当前元素”，放弃则只丢当前未保存修改。返回详情仍保存并返回。保存中按钮禁用，失败在弹窗内可见并保留输入。

父页面每次用新返回版本推进后续保存，当前曲线的规范文档来自服务器响应；其他分波保留原GET/manual的身份已校验文档。编辑器将已保存文档作为新的基线。父页面在编辑器退出且上下文一致时才替换背后详情与URL，原图blob不会因连续保存被撤销。数据本身每次POST成功即已入库，不是延迟提交。

## 测试与构建

- 15个文件、109项前端测试通过，包括6项新增保存切换组件测试。
- 前端生产构建通过；现有大包/3Dmol eval提示不变。
- git diff --check通过；用户既有联动参数及Demo共27个源文件哈希未变。
- 未修改后端或数据库结构，本轮没有重跑后端全套；真实版本写入由下述HTTP/SQLite场景验证。

## 浏览器

实际本地Vite 5173，全部API重定向至8198专用FastAPI/SQLite；数据库与文件位于/tmp/scwiki-manual-test-save-continue-v2/。没有向业务API写测试数据。

新增6组场景通过：
1. H保存12后直接进入Sc，编辑器不关闭；数据库H已更新而Sc保持。
2. 保存切换后隐藏/显示原图，blob仍可实际解码。
3. Sc保存18后进入La，下一次请求base_run/集合版本等于上次成功响应；回切H/Sc分别读到12/18。
4. 发送前网络失败保留H的13输入，数据库仍12；390px错误可见；重试成功并在保存中禁用重复操作。
5. 取消仍留当前元素，放弃仅丢未保存19，回切读到已保存13，无额外写入。
6. 真正退出保存La=8并返回；URL更新、刷新后H=13/Sc=18/La=8全部保留。

复跑既有12组版本浏览器场景也通过，包括跨页自动恢复、并发旧保存409及未保存输入保护、网络响应丢失后刷新恢复和错误身份拒绝。两套pageerror均为零。
首轮新浏览器脚本将主工具栏与弹窗内两个“正在保存…”按钮混为同一定位，收窄到弹窗后在新隔离库完整复跑通过；不是应用功能故障。

[新增机器报告](assets/save-continue-validation/save-continue-browser.json) · [版本回归报告](assets/save-continue-validation/version-browser-validation.json) · [切换弹窗](assets/save-continue-validation/save-and-continue-dialog.png) · [窄屏失败保留](assets/save-continue-validation/mobile-save-failure.png)。

复验：使用新/tmp/scwiki-manual-test-前缀目录，DATABASE_URL指向内部SQLite，FILE_STORAGE_BACKEND=local，FILE_STORAGE_LOCAL_ROOT与SCWIKI_MANUAL_TEST_ROOT均在该临时目录；启动backend.tests.manual_editor_server:app端口8198，设置SCWIKI_SPECTRUM_BROWSER_OUT后运行tests/01_decentralized_uploading/spectrum-save-continue-production.cjs。版本脚本可用SPECTRUM_TEST_BACKEND=http://127.0.0.1:8198复验。具体构建/单元命令与前一auto-latest-validation.md相同。

## 边界

新保存继续流程保持服务端版本保护，不自动合并并发修改。网络结果不明时不绕过旧版本检查。图像资源和只读详情在退出时同步，业务数据每次即时保存。截图原图已归档、哈希/尺寸/解码检查通过。
本地已热更新，未推送、未操作其他部署环境，未修改用户业务谱。远程文档链接仍待授权推送后验证。
