# 普通查看自动恢复最新结果验收

日期：2026-10-27，Asia/Shanghai。关联[#161](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/161)。

## 根因与修改

旧页面将URL中的run/collection_version与当前列表版本不一致视为mismatch，清空validItem，普通刷新因而被挡在“打开最新结果”提示。重新读取只重新GET，不能修复URL。

现将身份校验与版本差异分开：身份一致时展示最新item，版本差异通过navigate(...,replace:true)同步地址。正在编辑、打开编辑器、历史查看和写操作中暂停导航。没有新增POST、后台轮询、数据合并或后端契约变化。后端版本保护不变，未保存编辑不被替换。

## 自动验证

- 14个文件、103项前端测试通过；包含两个旧URL版本场景自动恢复/replace后退栈验证、错误材料/曲线拒绝、历史查看保持及谱编辑/计算回归。
- 前端生产构建通过，现有大包/3Dmol eval提示保留。
- git diff --check通过；参数和Demo共27个源文件哈希与实施前基线一致。
- 后端没有代码修改，本轮未重新运行后端全套测试；并发版本保护由下述真实HTTP流程覆盖。

仓库根命令：

    DEBUG_PRINT_LIMIT=500 npm --prefix frontend run test:upload-ui -- tests/01_decentralized_uploading/spectrum-*.test.tsx tests/01_decentralized_uploading/property-spectra-navigation.test.tsx tests/01_decentralized_uploading/upload-spectrum-save-navigation.test.tsx
    npm --prefix frontend run build

## 浏览器与真实HTTP流程

使用实际本地Vite 5173，所有API重定向至专用8197隔离FastAPI/SQLite，数据库和文件均位于/tmp/scwiki-manual-test-auto-latest/；未写业务谱。12组场景通过，无pageerror：

1. 版本未变的刷新正常且地址不变。
2. 同页重算更新地址后刷新正常。
3. 另一标签页重算后，旧页刷新自动加载最新结果及URL，无额外选择或写请求。
4. 重用旧链接自动恢复，无恢复按钮。
5. 同页人工保存并刷新，点数据持久化。
6. 跨页人工保存后旧页刷新自动恢复。
7. 跨页并发编辑仍409，未保存幅值0.09保留且不覆盖已保存0.08。
8. 请求发送前网络失败不产生新运行，显式重试成功。
9. 服务端已提交但响应丢失，刷新恢复已保存结果，不重复POST。
10. DOS跨页旧版本同样自动恢复。
11. 390px旧链接直接显示结果，无页面整体横向溢出。
12. 错误材料身份仍拒绝，不展示编辑器或跳转其他材料。

[机器报告](assets/auto-latest-validation/version-browser-validation.json) · [旧链接刷新后正常详情](assets/auto-latest-validation/version-auto-latest-after-refresh.png) · [窄屏](assets/auto-latest-validation/version-mobile-auto-latest.png) · [未保存编辑保护](assets/auto-latest-validation/version-unsaved-conflict-preserved.png)。

## 范围与限制

本次收敛此前V1/V2及V3“刷新后仍被旧URL阻断”的体验问题，不改为自动重试写请求，也不引入原模块焦点自动刷新。不同谱集合仍按原历史规则处理，不自动跨材料或跨集合猜测身份。显式历史选择器继续可用。

本地5173已提供新代码，无需额外重启。未推送、未操作阿里云/Docker、未回填或修改用户业务数据。用户截图已原字节归档并完成哈希、尺寸及解码验证。远程Spec链接仍待推送授权后核验，不据本次验证关闭全部#161事项。
