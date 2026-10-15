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

## 2026-10-15：配对单行实施验收

本节取代旧的 400/640px 多列断点验收。用户已在看到最终 Demo 后明确“认可，开始落地”。原图、取色与获认可 Demo 见 [附件清单](assets/images.json)，当前实现见 [真实浏览器截图](assets/tc-paired-implemented.png)。

- 前端 9 文件 113 项通过，覆盖当前 Tc、参数前置、两组 μ*、交换大小次序但不移动输入组、零值/清空/非法参数、类型切换、只读、详情参数摘要及核对定位。`tc-paired-parameters.test.tsx` 的真实表单回调载荷继续送入后端往返。
- 后端 4 文件 22 项通过：已有模块与条件校验、参数有效性，以及真实前端载荷/12 份浏览器保存请求经生产 `persist_property_modules`、SQLite 写入、新会话读取和导出。该记录证明隔离 SQLite 链路，不等同于本轮 MySQL 或生产环境验收。
- Chrome 在管理员、超级管理员、上传三入口各完成 4 次隔离保存；页面错误均为零。测量输入在 700/640/500/400/350px、预测输入在 1100/700/375px 检查单行与局部滚动。两组底色均为 RGB(244,243,255)，分组边框为 0px，保存/重载后 μ* 与 Tc 仍对应；上传只读态的 Tc/μ* 禁用。
- 现有核对侧栏已在 #138 中取消 JSON 展示，本轮浏览器检查改为识别当前人工编辑、保存失败保留理由、成功完成后关闭及位置保持；不是依赖已退役的 JSON 文案。上传夹具没有待核对记录时 `needs_check=false`，不发起模型任务。
- TypeScript 和生产构建通过；既有 3Dmol eval、分包体积及依赖弃用告警仍存在。
- 所有浏览器 API 请求均被隔离夹具拦截，未操作真实论文、调用真实模型、执行数据库迁移或部署；未推送，新版 Spec 的远程链接保持待验证，Issue 不关闭。

复查入口：`tests/01_decentralized_uploading/tc-record-browser.mjs`、`tc-paired-parameters.test.tsx`、`backend/tests/test_tc_paired_parameters.py` 和 `tests/01_decentralized_uploading/test_tc_record_roundtrip.py`。浏览器脚本使用 `PLAYWRIGHT_MODULE`、`CHROMIUM_PATH`、`TC_BROWSER_PAYLOADS`、`TC_PAIRED_SCREENSHOT`，后端测试以 `TC_PAIRED_PAYLOAD` 接收前端表单载荷。隔离环境使用 SQLite URL 及专用测试 JWT，不能复用生产密钥。

### 提交范围的独立验证

本次仅暂存明确文件及分块，从暂存区构造隔离副本，排除原工作树 #120/#135/#137 的未提交修改。该副本前端 9 文件 112 项、生产构建、三个真实浏览器入口及 12 次保存均通过；其中前端比完整工作树少的 1 项是原有未提交的研究驱动力冲突测试，不属于本增量。当前截图和 [保存记录样例](assets/tc-paired-saved-record.json) 来自隔离夹具，均不是真实论文数据。

后端相关校验/持久化/导出 21 项通过，另 1 项上传提取测试 `test_worker_prompts_and_storage_keep_each_measurement_conditions` 的旧夹具缺少 `user_id`，在隔离副本与替换为 HEAD 原始 `property_modules.py` 的基线中均以相同 KeyError 失败。该提取流程未在本轮修改，此失败不计为通过；没有把工作树里另一任务的夹具修复混入提交。本轮的独立数据库验收包括新配对参数测试以及 12 份浏览器保存请求的生产持久化和导出路径。

## 统一四模块正式实现验收（US6～US9）

用户认可最终整合 Demo 并明确要求“先把 issue 和 spec 写好”，本轮先同步 #94 与 Spec/Plan/Research/模型/契约/T020～027，再修改真实 React 表单、后端校验及页面路由。保留此前 Demo 的历史验收边界，最新实施基线见 Spec 末节。

### 已验证路径

- 从精确暂存内容生成独立候选目录，排除工作树 #120/#135/#137 未提交修改。前端 14 文件共 144 项通过；顺序调整后的旧测试改为按参数锚点定位，相关 2 文件 33 项复验通过。工作树原有额外 1 项研究驱动力测试不计入本次提交。
- TypeScript 与前端生产构建通过，保留既有 3Dmol eval 和大分包告警。候选不导入尚未提交的 SpectrumWorkspace，不需要其源码才能构建。
- Chrome 的上传、管理员、只读三个真实路由全部通过，页面错误均为 0。前两个入口各 3 次隔离科学数据保存，分别验证“保存并完成”先保存主值、再保存说明并自动上传待上传文件；未调用 AI 或正式审核。谱详情分别打开 DOS/α²F、刷新页面、读取材料条件、导出并返回，主表单字段保持；保存失败阻止跳转。
- 浏览器验证字段初始 110px、长中英文超过 350px、清空回缩至 110px；连续补充条件逐条另起一行。375px 的 Tc 卡片仅行内滚动、输入保持单行，整页不被撑宽。材料标题在修改及折叠后保持空间群/化学式/压强。
- ΔH 试填 0.025 eV/atom、ΔG 试填 0.018 eV/atom / 500 K，切换依据后分别恢复；这些仅是隔离夹具，未进入产品默认数据。真实保存请求被逐记录送入生产后端校验，热力学记录经 SQLite 写入、新会话重读和完整材料状态导出后保留全部 cases。
- 后端 4 文件 36 项通过，另 1 项既有上传提取测试单列：test_worker_prompts_and_storage_keep_each_measurement_conditions 的旧夹具缺 user_id。本次候选和换回 HEAD 原始 property_modules.py 都以同一 KeyError 失败，未修改该旧夹具，也未计为通过。

复查脚本：[unified-property-browser.mjs](../../../tests/01_decentralized_uploading/unified-property-browser.mjs)、[前端交互](../../../tests/01_decentralized_uploading/unified-property-modules.test.tsx)、[谱路由](../../../tests/01_decentralized_uploading/property-spectra-navigation.test.tsx)、[后端往返](../../../backend/tests/test_thermodynamic_stability.py)。浏览器配置沿用 PLAYWRIGHT_MODULE、CHROMIUM_PATH、FRONTEND_URL，PROPERTY_BROWSER_OUTPUT 指定证据目录；后端测试以 PROPERTY_BROWSER_PAYLOADS 接收该目录的 payloads.json。

[正式组件布局截图](assets/unified-property-implemented.png)与[独立详情截图](assets/spectrum-detail-implemented.png)来自上述隔离夹具，不是业务论文或真实谱提取结果。实际请求中的[热力学记录样例](assets/unified-property-saved-record.json)及[三入口结果](assets/unified-property-browser-results.json)作为验收产物留存。

### 目标环境边界

浏览器 API 使用隔离夹具；数据库往返使用 SQLite。未操作真实论文、未执行 MySQL/谱库迁移、未调用真实模型或部署。谱详情前端已消费 #137 的目标鉴权、原图/导出及版本合同；真实谱 API、采纳裁剪和目标数据库就绪仍由 #137 验收，不能据本轮 mock 宣称后端部署完成。#94 更新版本未推送，远程 Spec 链接待验证，Issue 保持 OPEN。

测试/构建日志与完整原工作树备份位于本机临时验收目录；它们是可复查记录，不承担协作状态。Issue 仍是未完成事项的状态来源。

## 四类性质模块默认折叠（US10）

用户补充要求后先同步 Issue/Spec，再将标量模块和仅谱模块接入同一个原生 details/summary 包装。默认折叠，鼠标或键盘分别切换；原有记录层 Accordion 保留。内容始终挂载，收起再展开不丢失输入，重排不串用模块状态；工具栏独立于标题，折叠不触发科学数据修改。

- 从精确暂存树构造隔离候选，16 文件 155 项前端回归通过，含 6 项模块折叠行为检查及仅谱模块检查；生产构建通过。未混入工作树原有研究驱动力测试及 #137 未提交源码。
- 隔离 Chrome 的上传、管理员、只读三个入口均验证四模块默认关闭，Enter 独立展开、Space 收起；前两个入口验证编辑内容在收起/展开后保留，并继续通过真实页面的保存请求、人工附件、谱详情打开/刷新/导出/返回回归，页面错误均为 0。
- 原 Tc 浏览器脚本也通过：管理员、超级管理员、上传入口各 4 次保存，页面错误均为 0；脚本在编辑内部记录前显式展开模块。
- 本轮仅修改前端和对应文档，不涉及后端数据合同或数据库迁移。新页面及详情返回重新挂载时按要求默认折叠；没有保存跨会话展开偏好。

[默认折叠效果截图](assets/property-modules-collapsed.png)和[三入口浏览器结果](assets/property-module-collapse-browser-results.json)来自隔离夹具。复查脚本仍为 unified-property-browser.mjs；本轮的折叠验证在展开模块后继续执行已有完整回归。

## 取消模块上下移动（US11）

历史核查：#90 的 T014 和 validation.md 记录了模块排序，#94 负责本轮表单迭代。因此将用户新原话及 IMG-006 追加到 #94，不重开历史 Feature 或创建重复 Issue。US11 取代用户通过上下箭头排序的旧交互，保留已有模块顺序及 display_order 合同。

- 移除共享模块编辑器的上下移动按钮、图标与 moveModule；删除空模块使用的序号归一化保留。折叠标题只为删除按钮保留必要空间。
- 精确暂存候选中 5 文件 59 项前端回归通过，覆盖已有非默认顺序、无移动入口、默认折叠、草稿保留、空/非空模块删除以及记录/谱详情行为；TypeScript 与生产构建通过。
- 上传、管理员、只读三个实际 Chrome 页面入口均断言上下移动控件不存在，并通过原有键盘折叠、编辑保留、保存和谱详情打开/刷新/导出/返回流程，页面错误均为 0。浏览器 API 为隔离夹具，本轮不操作实际论文或迁移数据库。
- 原图从归档位置经过 PIL 解码、像素尺寸及 SHA-256 验证；附件内容仅用于定位箭头，不作为额外指令。

[移除上下箭头的页面截图](assets/property-modules-no-move.png)、[三入口结果](assets/property-modules-no-move-browser-results.json)。复查脚本为 unified-property-browser.mjs，前端断言见 material-states-editor.test.tsx 和 property-module-collapse.test.tsx。本轮保留共享工作区已有修改，仅提交本需求；未推送，远程 Spec 继续待验证。

## US12 两行布局 Demo 验证

已按本轮用户两次答复演示：新建类型只选理论/实验/未说明，新增项属于结构优化核处理。旧 mixed、正式枚举、结构模型及生产表单均未修改，当前等待 Demo 评审。

Chrome 验证：1024px 和 736px 第一行均为七个同排字段；理论模式第二行四项同排，实验/未说明隐藏并禁用结构核处理；切回理论恢复 SSCHA 试填。化学式 H3S 自动变为两种元素，Im-3m 联动 229/立方，压强改为 180 GPa 后摘要更新；折叠不丢失输入。320px 无页面横向溢出，暗色模式可读，页面错误为 0。

本轮只验证浏览器本地交互，不等同于保存/迁移或真实科学结果。预览脚本由 visualize 的 render.py 生成包装并在 iframe 内验证；可读留档、截图及观测值见本目录 assets/material-state-two-row-demo.html、material-state-two-row-demo.png、material-state-two-row-validation.json。

## US13 三行固定高度 Demo

本节取代 US12 上一轮两行 Demo 的布局结论，旧记录保留为历史。结构家族独占第三行；空值、单项、17 标签及长英文标签时框高均为 43 CSS px，新增标签水平排列，超宽仅内部滚动。1024px 第一行七项同排，理论第二行三项，第三行为结构家族；736/320px 均无整页溢出，框高不因标签数量变化。

Chrome 进一步验证：追加超过 8 项仍可继续，回车添加、Backspace 删除、逐项删除、理论/实验显隐和试填恢复保持；暗色正常，页面错误为 0。标签是示例分类，不绑定真实论文；本轮未执行数据库操作。原“旧 mixed 后续兼容处理”方案被最新全面退役意图取代，不宣称正式数据清理已经完成。

演示留档：assets/material-state-three-row-demo.html；多标签截图和观测值见同名前缀 PNG 与 validation.json。原两行 Demo 留档仅供比较，最新评审使用三行版本。
