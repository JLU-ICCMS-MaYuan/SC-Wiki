# 验证步骤

本轮仅文档创建，以下为实施后的执行路径，尚未运行。

## 前置条件

在mayuan核对工作区，记录正式与Demo的dragInfluence.ts当前哈希以确认不被修改。使用隔离谱后端、临时文件和SQLite，不向业务数据库写测试数据。已有正式浏览器夹具为backend/tests/manual_editor_server.py；参考 tests/01_decentralized_uploading/spectrum-insert-production.cjs 和 spectrum-chain.test.tsx 的事实边界。

## 自动测试

从frontend目录执行：

    npm run test:upload-ui -- tests/01_decentralized_uploading/spectrum-tool-interactions.test.tsx tests/01_decentralized_uploading/spectrum-chain.test.tsx tests/01_decentralized_uploading/spectrum-insert.test.tsx tests/01_decentralized_uploading/spectrum-manual-editor.test.tsx
    npm run build

新测试文件须在实施时创建；本轮不把不存在的测试命令标为通过。

## 正式页面验收顺序

1. 打开α²F编辑器，所有持续工具初始浅色。点选只查看，左键拖动不移动点。
2. 点击联动按钮变深色，拖动影响相邻连接点；点击同按钮退出变浅色；单点按钮只动目标点。
3. 清空选择后激活增加点，悬停已有点附近出现预览，第一次点击只选起点；下一次点击才新增点。
4. 检查原直连插点、未连接点补接、无候选、其他分波、重复点击、双击结束与重新进入。
5. 逐个测试平移、框选、零频、标定取点的同钮退出/异钮切换/Esc及手势取消；保存/删除/撤销仍立即执行。
6. 在DOS、横/纵频率轴及不同缩放重复；390px窄屏检查按钮可达、不造成页面整体横向溢出。
7. 检查默认/选中/悬停/焦点/禁用的计算样式，选中为主题深色、未选中浅色，aria-pressed同步；保存刷新与撤销回归。
8. 记录实际验证与截图到validation.md；不得将本计划视为测试证据。
