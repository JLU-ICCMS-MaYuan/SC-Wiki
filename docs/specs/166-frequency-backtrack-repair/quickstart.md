# 验证步骤

使用scripts.local_deploy.environment指定仓库目录定位Python。设置测试SQLite和固定测试JWT，运行新增frequency_repair及现有spectra系列pytest；不连接业务库。
frontend运行针对频率修正/撤销及编辑器的Vitest和npm run build。
浏览器使用临时SQLite/文件与专用测试端口，将所有API重定向隔离正式后端。合成已手动修订的微小回折，点击重新计算并检查新版本及点高亮，打开编辑器撤销、保存，再次计算应保留撤销意图。另验证超过限额、后续人工频率编辑和无修正情况。
实际命令、结果和范围在validation.md记录；本步骤不代表已通过。

## 可复验的浏览器入口

创建新的/tmp/scwiki-manual-test-前缀目录和browser子目录，DATABASE_URL指向目录内SQLite，SCWIKI_MANUAL_TEST_ROOT指向该目录；FILE_STORAGE_BACKEND=local、FILE_STORAGE_LOCAL_ROOT指向其files子目录，JWT_SECRET_KEY使用固定测试值，SCWIKI_INSERT_VERTICAL_FIXTURES=1、SCWIKI_RECALCULATE_TEST_FIXTURES=1。启动python -m uvicorn backend.tests.manual_editor_server:app --host 127.0.0.1 --port 8196；在frontend启动npm run dev -- --host 127.0.0.1 --port 5175 --strictPort。设置SCWIKI_SPECTRUM_BROWSER_OUT为browser目录后运行node tests/01_decentralized_uploading/spectrum-frequency-repair-production.cjs。测试会写隔离数据，完整复验建议新目录。实际结果见[validation.md](validation.md)。
