# 验收：晶系未知联动

## 环境与安全

仅使用隔离夹具。浏览器拦截全部 API，不写真实论文 #29；Python 使用内存 SQLite。
开工已有 81 个跟踪文件修改及多个未跟踪文件，已记录在 `/tmp/scwiki-crystal-unknown-baseline-b0yXJZ/`，不得混入本次提交。

## 执行命令

```bash
node "frontend/node_modules/vitest/vitest.mjs" run --config "vitest.config.ts" "tests/01_decentralized_uploading/crystal-unknown-reset.test.tsx" "tests/01_decentralized_uploading/material-states-editor.test.tsx"
DEBUG=false DATABASE_URL="sqlite://" RAG_DATABASE_URL="sqlite+aiosqlite:///:memory:" JWT_SECRET_KEY="test-only-secret" /home/mayuan/miniconda3/envs/sc-wiki/bin/python -m pytest "tests/01_decentralized_uploading/test_crystal_unknown_reset.py" -q
PLAYWRIGHT_MODULE="/tmp/sc-wiki-browser/playwright/driver/package/index.mjs" CHROMIUM_PATH="/home/mayuan/.cache/ms-playwright/chromium-1223/chrome-linux64/chrome" node "tests/01_decentralized_uploading/crystal-unknown-browser.mjs"
npm --prefix "frontend" run build
```

## 验收步骤

1. 两入口加载含两个材料状态的隔离论文/草稿；确认加载本身不清理空间群。
2. 第一项选择未知，确认符号和编号清空、第二项与结构不变；再次选择和键盘重复。
3. 输入符号后失焦、切换未知，确认不会回填；保存请求含三字段当前值。
4. 保存失败保留清空状态，再次保存并刷新后保持；后端持久化测试核验真实 null。
5. 重新选择有效标准符号或输入有效群号，确认原正向联动正常。
6. 核对回归验证字段变化通知及旧版本隔离；不调用 AI 或正式批准。

## 验证记录

### 2026-09-17

- 红测：先运行新增 8 项交互测试，确认 5 项因缺少联动失败，分别覆盖三字段残留、重复选择、本地文本、后续候选选择及重复空态操作；修复前未写业务代码。
- 共用组件修改后，新增 8 项与原有材料状态 25 项全部通过。
- 扩展前端：`crystal-unknown-reset`、`material-states-editor`、`evidence-workflow`、`scientific-evidence-markers`、`upload-task-editor-layout`、`admin-edit-page` 六文件共 **97 项通过**。
- 扩展后端：`test_crystal_unknown_reset.py`、`backend/tests/test_space_groups.py`、`test_scientific_evidence.py`、`test_evidence_proposals.py` 共 **28 项通过**。
- 新增后端 4 项覆盖：重复归一化、已知群号仍可推导晶系、空核对项移除与相关物性断言变化、真实科学保存事务及新会话读取。清空后再次保存判为同值，修改历史存在；新上传持久化亦保持空值。未修改后端生产代码。
- Chromium 三模式 `admin`、`superadmin`、`upload` 均通过：鼠标重复选择、键盘首次及重复选择、符号失焦不回填、500 失败保留输入、重试请求的显式 null、刷新和有效空间群重新选择。所有 API 使用隔离夹具，无 AI、人工确认提交或正式批准请求，无页面脚本错误。
- `npm --prefix frontend run build`（含 `tsc -b`）通过。保留现有依赖告警：Vite CJS、React Router future flags、Python crypt/spglib 弃用、3Dmol eval 及大包提示；无本次类型或构建错误。
- `git diff --check` 通过。
- 独立只读代码复核未发现本次增量引入的阻断问题；复核者独立重跑新增前端 8 项和后端 4 项，全部通过。
- 三个重叠文件以开工备份生成补丁，经 `git apply --cached --check` 校验后只暂存本次增量；新增测试与 Spec 按明确路径暂存。既有材料名、压强、Tc 等未提交修改不纳入本次提交。

## 交付边界

上述验证基于当前工作树，含开工前已存在的未提交功能；没有部署生产环境，也未执行真实 MySQL、Redis 或论文 #29 写入。
浏览器验证页面与请求，后端隔离 SQLite 验证实际科学数据保存与重新读取；不把浏览器 Mock 当作数据库证据。
HEAD 原本已引用尚未跟踪的 `evidenceFields.ts`、`PressureEditor.tsx` 等文件，本次不补交这些前序文件，
也不宣称当前 HEAD 可独立干净构建。仅按开工备份分离本次晶系逻辑、测试和文档增量。
