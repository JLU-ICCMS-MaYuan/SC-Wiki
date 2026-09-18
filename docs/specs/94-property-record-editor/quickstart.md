# 快速验收

## 自动验证

在项目根目录使用已有依赖：

```bash
node "frontend/node_modules/vitest/vitest.mjs" run --config "vitest.config.ts" "tests/01_decentralized_uploading/property-record-editor.test.tsx" "tests/01_decentralized_uploading/material-states-editor.test.tsx"
(cd "frontend" && node "node_modules/typescript/bin/tsc" -b)
DATABASE_URL="sqlite://" JWT_SECRET_KEY="test-only-secret" "$HOME/miniconda3/envs/sc-wiki/bin/python" -m pytest "backend/tests/test_property_record_conditions.py" "backend/tests/test_property_modules.py" "backend/tests/test_upload_jobs.py" -q
```

Python 测试使用 SQLite 内存数据库，不触碰开发数据或真实 LLM。

## 界面路径

1. 上传校对或管理员编辑页打开一个材料状态，添加测量 Tc、预测 Tc 和自定义性质。
2. 确认菜单和标题无模板版本后缀；测量 Tc 只显示一个实验条件多行框。
3. 填写两条不同条件，分别折叠/展开；修改、复制和删除一条，确认另一条保持不变。
4. 保存后再次读取，确认文本及换行保留；只读详情可折叠且不可编辑。
5. 打开旧结构化条件，确认内容可读；编辑后原始字段与 Evidence 仍在导出数据中。

真实 LLM 输出质量需用具体论文复核；自动测试证明提示词接入和实际数据通路，不声称覆盖外部模型每次生成。

## 本次验证结果（2026-09-08）

- 前端 48 项通过：本功能 6 项、共享材料状态 25 项、管理员科学数据编辑 5 项、管理员数据展示及详情字段一致性合计 12 项。
- 后端 62 项通过：本功能提取到数据库及导出往返、描述类型与空值、模块持久化、上传归一化和材料状态导出。
- TypeScript 项目编译通过。
- 上述为本地自动验证，不代表生产部署或真实 LLM 对特定论文的准确率。

## Tc 紧凑布局验证（2026-09-16）

本节保留原方案验证记录；其中原始记录保留规则已被下方“当前 Tc 唯一来源”验收取代。

```bash
node "frontend/node_modules/vitest/vitest.mjs" run --config "vitest.config.ts" \
  "tests/01_decentralized_uploading/tc-record-layout.test.tsx" \
  "tests/01_decentralized_uploading/property-record-editor.test.tsx" \
  "tests/01_decentralized_uploading/material-states-editor.test.tsx" \
  "tests/01_decentralized_uploading/paper-detail-form-parity.test.tsx" \
  "tests/01_decentralized_uploading/upload-task-editor-layout.test.tsx" \
  "tests/01_decentralized_uploading/evidence-drawer-close.test.tsx" \
  "tests/01_decentralized_uploading/scientific-evidence-markers.test.tsx" \
  "tests/01_decentralized_uploading/evidence-workflow.test.tsx" \
  "tests/02_identity_governance/admin-edit-page.test.tsx"
TC_BROWSER_PAYLOADS="/tmp/scwiki-tc-layout-payloads.json" \
  node "tests/01_decentralized_uploading/tc-record-browser.mjs"
DEBUG=false DATABASE_URL="sqlite://" JWT_SECRET_KEY="test-only-secret" \
  TC_BROWSER_PAYLOADS="/tmp/scwiki-tc-layout-payloads.json" \
  "/home/mayuan/miniconda3/envs/sc-wiki/bin/python" -m pytest \
  "tests/01_decentralized_uploading/test_tc_record_roundtrip.py" \
  "backend/tests/test_property_record_conditions.py" "backend/tests/test_property_modules.py" -q
(cd "frontend" && npm run build)
```

浏览器脚本需要已有 Vite 服务，FRONTEND_URL 默认 http://127.0.0.1:5173；可用
PLAYWRIGHT_MODULE 和 CHROMIUM_PATH 指定已有 Playwright/Chromium。TC_SCREENSHOT 可选，
保存默认卡片截图。所有 API 使用隔离夹具，没有写入论文 #29，也没有调用 AI 或正式批准。

- 114 项相关 Vitest 回归通过；先运行新增测试确认旧界面失败，再验证修复。
- Chromium 的管理员、超级管理员、上传校对三条路径通过；卡片内容宽度 700/640/500/400/350px
  的列数与溢出检查通过。原始记录默认隐藏，只读仍可展开；实验条件保持整行。
- 完整小数、临时指数、原生粘贴、清空、零值、代表标记、范围、保存重载均通过；两个材料状态
  的结果独立。管理员核对侧栏展示当前 Tc，失败保留理由，重试成功后关闭且位置不变。
- 9 份浏览器成功保存请求经生产校验、SQLite 写入、重新读取和导出逐字段比对通过；
  另有 10 项现有后端回归通过，合计 11 项。
- 完整工作树 TypeScript 与生产构建通过；既有 3Dmol eval 和产物体积告警仍存在。
- 扩展运行 submit-validation-feedback.test.tsx 时有 8 项失败，在开工前代码快照中同样复现：
  旧材料身份文案和核对准备请求替身未跟进先前改动；不计作本次通过项，关联 #103 跟进。

### 提交边界

开工快照保存在 /tmp/scwiki-tc-layout-baseline-oQX5r4，包含原有 tracked diff 和重叠文件。
本次补丁为该目录 tc-only.patch；候选 index 仅包含本次明确文件及增量，保留此前标签锚点修改。
候选副本的 Tc、记录与详情测试 24 项通过，但上传测试加载和 TypeScript 构建失败：当前 HEAD
已引用尚未提交的核对依赖，独立提交无法闭合。完整工作树验证不等于独立 Git 提交验证。
按 AGENTS.md 规则不提交、不推送、不切换分支；原有改动和实际 index 保持原状。

## 当前 Tc 唯一来源（2026-09-16 用户澄清后）

先运行本次新增失败测试，再实施移除原始记录、前后端当前值同步及核对兼容。
沿用上方前端命令并加入 evidence-proposals.test.tsx；浏览器输出改为
/tmp/scwiki-tc-current-payloads.json，后端验证命令如下：

```bash
DEBUG=false DATABASE_URL="sqlite://" JWT_SECRET_KEY="test-only-secret" \
  TC_BROWSER_PAYLOADS="/tmp/scwiki-tc-current-payloads.json" \
  "/home/mayuan/miniconda3/envs/sc-wiki/bin/python" -m pytest \
  "tests/01_decentralized_uploading/test_tc_current_value.py" \
  "tests/01_decentralized_uploading/test_tc_record_roundtrip.py" \
  "backend/tests/test_property_record_conditions.py" "backend/tests/test_property_modules.py" \
  "tests/01_decentralized_uploading/test_evidence_proposals.py" -q
```

- 前端 127 项通过，其中 Tc 单入口、规范化与核对路径 17 项。新建只填当前值，数字零、范围、
  文本、布尔及科学计数法正确生成兼容表示；输入中的半截指数不会回填旧值。
- 后端上述 41 项通过，包含 9 份浏览器保存请求经真实生产校验、SQLite 写入、新会话读取与
  导出比对。缺 raw 可保存；旧 raw 不能掩盖缺失或无效当前值，NaN/Infinity/布尔冒充数字被拒绝。
- 核对 expected_claim 与保存后的科学断言一致，修改建议后同步 raw，不提供第二份 raw/单位编辑；
  旧字段核对定位到当前控件，稳定身份不变。
- Chromium 管理员、超级管理员及上传路径全部通过；无原始记录及重复值入口，五种卡片宽度
  无溢出。人工理由失败保留、成功关闭且位置不变，未调用 AI 或正式批准。
- TypeScript 与生产构建通过；既有 3Dmol eval、产物体积和 Python 依赖弃用告警仍存在。
- 扩展后端回归 71 项通过、13 项因未启用 MySQL 跳过、1 项失败：
  test_upload_jobs.py 的 test_submission_rejects_unknown_paper_type_but_accepts_pending_material_family
  使用 Example2H3 假化学式，与前序材料名/化学式解析规则不符。加载本轮开工前的
  property_modules.py 后同一测试仍失败，未改该测试或放宽科学校验；关联 #103 跟进。
- 不修改真实论文 #29，不执行数据库迁移、批量数据改写或生产部署。

### 本轮提交边界

开工快照位于 /tmp/scwiki-tc-current-baseline-yMJpXr。复查当前 HEAD 仍引用不在 Git 中的
evidenceFields、evidenceProposals、PressureEditor、EvidenceFieldMarkers；本次调整的 TcRecordFields
及核对模块也与前序未提交实现交叠。不能通过整文件暂存混入旧改动。沿用 T011 的提交阻塞，
本轮保留工作树修改与空暂存区，不创建分支、不推送；本地验证不能视为独立提交或生产部署。

## 2026-09-17 必需依赖分批交付

本轮用户明确授权将 #103 必需的 Tc 依赖单独提交，不包含自定义模块扩展。Tc 输入、规范化与
保存校验为依赖批次；核对字段定位、建议准备及其集成测试随 #103 批次交付。完整应用的验证
以排除无关改动后的合并候选树为准：49 文件、396 项前端回归和生产构建通过；Python 专项
152 项通过、27 项因未配置专用数据库跳过，其中包含 9 份本轮浏览器请求经 SQLite 写入和
导出重载。Chromium 在上传、管理员、超级管理员分别完成三次保存，页面错误均为零。
旧失败的提交提示、Tc 标签及测试请求替身已经跟进当前契约，未放宽业务校验。
本轮不改真实论文、不执行数据库迁移、不推送；历史提交阻塞记录保留，不再代表本轮结论。

独立 Tc 候选 index 的定向验证为前端 23 项、Python 33 项通过；其中暂不包含依赖 #103 的
核对集成用例。既有 HEAD 缺失的科学核对依赖由下一批补齐，上述应用级验证不省略该批次。
