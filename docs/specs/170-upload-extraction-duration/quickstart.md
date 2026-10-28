# 验证说明

前置条件：项目Conda Python与frontend/node_modules已安装；浏览器脚本使用现有Playwright与Chrome。无需真实模型调用或修改业务任务。

1. 使用 `python3 -m scripts.local_deploy.environment "/Users/mayuan/Codes/SC-Wiki"` 定位Python。
2. 执行 `python -m pytest tests/01_decentralized_uploading/test_upload_extraction_timing.py`，预期状态与持久化边界通过。
3. 在frontend运行 `npm run test:upload-ui -- tests/01_decentralized_uploading/upload-extraction-timing.test.tsx`，验证运行/终态/刷新/乱序响应。
4. 在frontend执行 `npm run build`，预期TypeScript及Vite通过。
5. 执行 `node tests/01_decentralized_uploading/upload-extraction-timing-browser.mjs`，使用第4步生产构建的独立预览服务器，隔离全部API，验证桌面/窄屏和中英文，输出 `/tmp/scwiki170-browser-output/` 截图，交付时归档本Spec assets/。

人工验收：205秒显示3分25秒；等待校对后不变；正文角色等待暂停；重新解析新一轮计时；旧任务显示未记录。浏览器隔离验证证明展示契约，不证明真实外部解析服务的科学正确性。

项目运行时：Python `/Users/mayuan/software/miniconda3/envs/sc-wiki/bin/python`、Node `/Users/mayuan/software/miniconda3/envs/sc-wiki/bin/node`。测试需要隔离的 `JWT_SECRET_KEY`；仅作为命令的进程环境传入。系统Node 26不适用于现有Vitest环境。
浏览器脚本通过 `PLAYWRIGHT_MODULE`、`TIMING_TEST_PYTHON` 指定已安装模块和Python路径，默认Chrome为本机Applications目录。
