# 验证操作

以下命令从仓库根执行。Python 先用 python3 -m scripts.local_deploy.environment "/Users/mayuan/Codes/SC-Wiki" 定位。

## 自动测试

    DATABASE_URL="sqlite:///:memory:" JWT_SECRET_KEY="isolated-dos-test-secret" /Users/mayuan/software/miniconda3/envs/sc-wiki/bin/python -m pytest backend/tests/test_spectra*.py backend/tests/test_alpha2f_relative.py -q

frontend 目录运行：

    npm run test:upload-ui -- tests/01_decentralized_uploading/spectrum-dos-relative.test.tsx tests/01_decentralized_uploading/spectrum-recalculate.test.tsx tests/01_decentralized_uploading/spectrum-relative.test.tsx tests/01_decentralized_uploading/spectrum-workspace.test.tsx tests/01_decentralized_uploading/property-spectra-navigation.test.tsx
    npm run build

## 隔离正式页面

每次使用新的 /tmp/scwiki-manual-test- 前缀目录，并创建其 browser 子目录。设置 DATABASE_URL 为该目录下 SQLite，SCWIKI_MANUAL_TEST_ROOT 为该目录，FILE_STORAGE_BACKEND=local，FILE_STORAGE_LOCAL_ROOT 为该目录的 files 子目录，JWT_SECRET_KEY 使用测试值。入口会拒绝不在临时目录内的存储根。

    python -m uvicorn backend.tests.dos_relative_server:app --host 127.0.0.1 --port 8194

另一终端在 frontend 启动专用 Vite：

    npm run dev -- --host 127.0.0.1 --port 5175 --strictPort

设 SCWIKI_SPECTRUM_BROWSER_OUT 为上述 browser 目录，从仓库根执行：

    node tests/01_decentralized_uploading/spectrum-dos-relative-production.cjs

预期：模式积分 4/5、预期 3/6、偏差保留；缺 N 时只显示面积/占比；刷新不会累乘；390px 无页面整体溢出。结果见 validation.md。退出后停止两个专用测试进程，不操作现有开发服务。
