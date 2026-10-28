# 验证步骤
1. 使用项目Python运行pytest tests/01_decentralized_uploading/test_evidence_progress.py及相关科学核对回归，状态后端采用隔离Redis，不连接业务数据。
2. 在frontend运行npm run test:upload-ui -- tests/01_decentralized_uploading/evidence-progress.test.tsx及相关用例；运行npm run build。
3. 以隔离HTTP/Redis夹具连接正式前端组件：观察准备0/5/10/20、完成2/5组50%、整理95%、终态100%；取消、失败及重试不自动提交，旧响应不覆盖。
4. 桌面和390px窄屏检查进度条、等待时间、文字换行、取消按钮及英文ARIA。
5. 记录实际命令和结果至validation.md，不将夹具验证称作业务数据验收或部署完成。

## 本次可复跑命令
项目运行时：/Users/mayuan/software/miniconda3/envs/sc-wiki/bin/python。
后端测试使用进程内测试JWT值（不是账户密钥），不加载业务.env：
```sh
JWT_SECRET_KEY="isolated-progress-tests-only" "/Users/mayuan/software/miniconda3/envs/sc-wiki/bin/python" -m pytest "tests/01_decentralized_uploading/test_evidence_progress.py" "tests/01_decentralized_uploading/test_two_stage_review.py" "tests/01_decentralized_uploading/test_property_evidence.py" "tests/01_decentralized_uploading/test_field_review_start.py" -q
npm --prefix "frontend" run test:upload-ui -- "tests/01_decentralized_uploading/evidence-progress.test.tsx" "tests/01_decentralized_uploading/two-stage-review.test.tsx" "tests/01_decentralized_uploading/manual-evidence-section.test.tsx"
npm --prefix "frontend" run build
```
浏览器验证先运行测试服务，再另开终端运行浏览器脚本：
```sh
"/Users/mayuan/software/miniconda3/envs/sc-wiki/bin/python" -m tests.01_decentralized_uploading.evidence_progress_bridge
PLAYWRIGHT_MODULE="/tmp/scwiki168-browser/node_modules/playwright/index.mjs" node "tests/01_decentralized_uploading/evidence-progress-browser.mjs"
```
浏览器脚本使用临时安装的Playwright与本机Chrome；可用PLAYWRIGHT_MODULE、CHROMIUM_PATH覆盖。后端默认本机8198，可用PROGRESS_TEST_PORT及PROGRESS_TEST_API同时更改；测试前端自动选择5198起的空闲端口。不要与前端构建同时运行，构建HTML变化会触发Vite重载。结束测试服务会自动清理隔离Redis与SQLite。
