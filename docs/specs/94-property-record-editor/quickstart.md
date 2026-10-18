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

## US12/US13 正式实施验收

已认可的三行 Demo 落到正式共享编辑器及只读详情。首行七字段同排；第二行类型、仅理论显示的结构优化核处理与压强；第三行固定高度结构家族。17 个长标签、删除/Backspace/清空前后输入框均为 53.125 CSS px；736px 不撑宽整页，新增后标签轨道滚到最右。类型仅理论/实验/未说明；从理论切出清空隐藏核处理。

### 独立候选证据

排除共享工作区 #120/#135/#137 的其他未提交改动，基于 HEAD 加本轮精确增量建立候选：

- TypeScript 及 Vite 生产构建通过，已有 3Dmol eval/体积提示保留。
- 前端 4 文件 64 项通过，包含三行、类型显隐/清空、mixed 拒绝、第二份几何禁止采纳、既有编辑/折叠/人工保存回归。
- Go models/handlers 的原生完整测试通过；部署脚本回归 44 项通过、11 项按环境跳过。
- 后端 6 文件 43 项通过，覆盖真实隔离 MySQL 写入、新会话重读、返修草稿、完整导出、同值/谱签名变化，以及数据库 CHECK/单几何唯一约束和迁移拒绝边界。SQLite 验证升级/降级保留行数。
- 上传、管理员、只读三个 Chrome 入口页面错误为 0。前两入口各经真实“保存并完成”控件发出 1 份隔离请求，刷新后 SSCHA 保留。HTTP 返回为隔离夹具，真实数据库往返由上述 MySQL 测试另证，不伪装端到端业务验收。结果及截图见 [浏览器结果](assets/state-implementation-browser.json)、[上传](assets/state-upload-basics.png)、[管理员](assets/state-admin-basics.png)、[只读](assets/state-readonly-basics.png)。
- 扩展的 material-name-review 1 条旧断言仍期待 Tin（Sn）标题，本轮候选及换回 HEAD 原组件均同样失败；当前标题使用既已批准的空间群/化学式/压强，此项不计入通过数。

### 数据库验证复现与边界

新迁移基于 0052/0137 两头。显式空隔离 MySQL 库用 [初始化脚本](assets/prepare-state-test-db.py) 建模型 schema，降回本次变更前，再合并升级到新头；设置 STATE_GEOMETRY_TEST_URL（库名必须包含 test）及 DATABASE_URL/JWT_SECRET_KEY，用项目 Python 以 PYTHONPATH=. 运行脚本。随后运行 backend/tests/test_state_geometry_contract.py 和 test_state_geometry_migration.py。脚本拒绝已有表，不删除数据库或业务记录。旧 ORM 的 JSON 字面默认值与 MySQL 8.4 CREATE TABLE 不兼容，仅在测试建库时省略。

完整历史 Alembic 链在空测试库推进时需按 #90 的空数据迁移服务通过观察门；其历史链生成的 superconductors 缺 paper_id，不能直接代替当前模型 fixture。该既有初始化边界没有在本次修改，不能声称历史链与当前模型已全面一致；本次迁移本身及当前模型上的真实保存分别验证。

### 本机应用前置

只读审计目标为本机 127.0.0.1:3307/scwiki，正式状态 0、规范结构 0，3 份持久化/Redis 上传草稿 mixed 0；新列尚不存在，仍为 0052/0137 两头。没有删除 mixed 数据，没有执行业务 schema 变更。

AGENTS.md 将“数据库结构变更”列为高风险操作。取得授权后：暂停后台及工作进程写入，确认无活动任务；重新备份数据库与草稿并记录 Alembic 版本；从已验证源码执行 python -m alembic upgrade 20261015_0094；核验列、三种类型 CHECK、单几何唯一约束、新迁移头和真实读取/保存 API 后恢复服务。遇迁移前置冲突先停止，不删数据或静默映射。需要回退时先恢复旧服务及维护状态，再按迁移前备份恢复；降级会移除新核处理列，必须保留备份，不能当作无损科学内容回滚。

业务迁移、部署、推送及远程 Spec 链接仍与本地代码交付分开，Issue 保持 OPEN。

本机维护已获用户明确授权“批准本机迁移并验证生效”；本节以上为代码交付前的验证记录，实际应用结果在完成后另行追加。

### 本机迁移与真实 API 已完成

用户明确授权后，先确认两个队列为空且无运行任务，再停止网关、Python、上传 Worker 与新闻工作进程；数据库与 Redis RDB 备份位于 `/Users/mayuan/SC-Wiki-backups/2026-10-15-162804-state94`，私有备份包含哈希、原迁移头和行数。文件/对象存储未改动。由本地提交 `fb7c8bd` 的独立归档源码执行迁移至 `20261015_0094`，完整 schema 校验通过，正式状态/结构均仍为 0，3 份持久化草稿数量保持。

服务已恢复：Python/Go health200、网关论文列表200；三份原有草稿分别返回16/6/7个状态，全部带合法类型及核处理字段。另对第一份草稿发出 mixed、非理论 SSCHA、同卡多规范结构三类无效 PUT，均400并带字段定位，前后数据库草稿及真实 GET 结果完全一致；没有保存新业务科学内容或调用模型。统一 UploadContractError 响应补齐部分入口原会误报500的边界，FastAPI 实际分发已加入回归。

[本机迁移及 API 证据](assets/state-local-migration.json) 留存备份哈希、全部迁移头、行数与匿名化 HTTP 结果。迁移源码为精确提交；本机服务沿用既有热重载方式读取共享工作区，其中仍包含其他任务的未提交内容，不能声称全部运行内容仅来自本次提交。没有推送或远端部署，远程 Spec 链接仍待验证。

## 2026-10-16：US14 费米能级 DOS 简化验收

- 先运行新增 DOS 行为用例，在“仍显示记录折叠标题”断言上复现失败；实施后通过。
- property-record-editor、unified-property-modules、tc-record-layout、material-states-editor 四份组件测试：62/62 通过。DOS 用例覆盖四项输入、无重复标题/定义选择/证据摘要、原始值与文本同步、定义/证据保留、复制删除及只读。
- 当前工作树 npm run build 通过（包含 TypeScript）；从 HEAD 导出 frontend 并只复制本次两份组件生成隔离副本，构建也通过：/tmp/scwiki-dos-candidate.BfX1AB/build.log。未纳入工作区其他任务的未提交修改。
- 原图 IMG-008、IMG-009 与清单已归档；Overview 已同步。现有测试夹具有 MUI 选项提示，构建有 3Dmol eval 与分包大小提示，均未导致失败。
- 本轮验证范围为组件行为与构建，未执行真实数据库修改、浏览器端到端验收、远端部署或推送；#94 保持开放，远程附件及 Spec 链接待推送核验。本轮没有修改远端 Issue 正文。

## 2026-10-16：US15 独立 Demo 评审准备

- 只读核对原任务历史备份：167 GPa 有三条 18.76 DOS，仅 record_key 不同，其中两条 record-copy-；证据完全相同。审计文件为 assets/fermi-dos-duplicate-audit.json，不据此宣称最新 Redis 已审计或已修复。
- 独立 HTML Demo 的浏览器检查覆盖：相同副本一行且无复制/重复新增；不同值待选择；选择后两候选保留；四输入与候选操作只读；空值；另一压强；来源侧栏；模块折叠后保留编辑。8 组观察均符合预期，控制台 error 为 0，默认 1280×720 无整页横向溢出。
- 截图 assets/fermi-dos-singleton-demo.png，记录 assets/fermi-dos-demo-validation.json；两者仅证明交互演示。冲突候选 19.10 为演示数值。
- Spec US15 是待评审草案，替代 US14 的直接实施流程。用户尚未认可本版 Demo/Issue 追加草案；本轮未修改正式代码、真实草稿、数据库或 Overview，未回退 e9d210a，未写入远端 Issue，未推送。

## 2026-10-16：US17 记录操作独立 Demo

从仓库根目录执行：

```sh
python3 -m http.server 18449 --bind 127.0.0.1 --directory "docs/specs/94-property-record-editor/assets"
```

访问 `http://127.0.0.1:18449/record-actions-demo.html`。该端口若正在提供本 Demo，可直接访问，不重复启动。

1. 默认建议方案无复制按钮，DOS 和 Tc 的删除均在本行右端。
2. 切到现有布局，复制 DOS 后得到两份相同数值；切回建议方案仍保留本方案的试填状态。
3. 删除 DOS 后 Tc 保留；恢复示例，再添加 Tc，新增数值为空。输入 DOS 18.80，折叠后展开，保留试填。
4. 选择 360px/760px 预览宽度，字段局部滚动、删除不移出右端；只读时输入禁用且无新增/复制/删除。

真实浏览器完成上述 8 组检查：默认及 360px 删除/输入中心差为 0 CSS px；360px/760px 无整页横向溢出；控制台 error 为 0。详见 [观测记录](assets/record-actions-demo-validation.json)和[截图](assets/record-actions-demo.jpg)。未跑生产构建，因为本次没有修改正式代码或依赖；检查不代表真实保存、四模块集成、数据库、部署或历史重复清理已验收。

用户已答复“认可设计并同步 #94，暂不落地”。本版 Demo 设计及完整追加正文获得认可，#94 已同步；通过 `gh issue view 94 --json title,body,state,labels,url` 读回核验：原正文保留、获批草案完整、追加最新答复，仍为 OPEN 且唯一类型为 `type:feature`。获批原稿仍保留其当时的待评审文案，Issue 末尾的最新结论优先。

本轮仅同步需求与文档，未修改正式代码、真实数据或 Overview，未推送；远程 Spec/图片链接仍待验证。整份 Spec 未经过另一次完整逐字确认，正式实施未获授权。

## US17 正式实施验收（2026-10-16）

用户在认可 Demo 和 Issue 正文后明确要求“开始落地！”，本次只实现 US17 的记录复制入口取消与同行删除，未实施 US15/US16。

- 共享组件：普通物性/DOS、Tc、热力学稳定性都接入 PropertyRecordRow；删除在字段滚动区外，移除 onClone 和仅供该入口的模块回调。原删除稳定键、元数据和底层深复制数据工具保持。
- 当前工作树相关 7 份测试共 100 项通过；从 HEAD 导出源码，仅复制本次 5 份组件与 1 份测试的隔离候选，同样 7 份/100 项通过。包括各类主行删除、只读、模块按键删除元数据、空白新增、折叠及其他记录未保存值保留、Tc 与来源核对/谱导航回归。
- 隔离候选 npm run build（含 TypeScript）通过；构建仍提示已有 3Dmol eval 和分包体积，未导致失败。不将共享工作树其他任务改动带入本次提交。
- 真实浏览器加载实际 PropertyModuleEditor 和共享表单，定义读取与样例独立；923px / 360px 容器中六类记录的删除与首个输入中心差均为 0 CSS px，按钮在行内，页面无横向溢出；360px 所有字段区均可局部滚动。只读无删除、所有可见输入/选择禁用；键盘删除预测 Tc 后只移除对应稳定键，保留 DOS 18.80 和测量 Tc 187 的未保存试填值。控制台 error 为 0。
- [浏览器记录](assets/record-actions-implemented-validation.json)、[正式组件截图](assets/record-actions-implemented.jpg)仅证明实际组件在隔离样例中的行为；未对业务草稿执行删除/保存，没有运行新的持久化测试或数据库迁移，不声称已部署远端。

验收副本与完整日志位于本机临时目录 `/var/folders/j8/21skwz6d3c1810rwvq3kpjf00000gn/T/scwiki-record-actions-implementation-b4_82k37/` 的 candidate，测试/构建日志为 `/tmp/scwiki-record-actions-candidate-tests.log`、`/tmp/scwiki-record-actions-build.log`。临时目录不是持久附件，关键截图和观察已归档。本次源文件 SHA-256 清单见浏览器验证记录，便于核对验收来源。

Overview 已同步实际按钮行为，#94 保持开放；本地 Spec/附件仍未推送，远程链接待验证。根 README 的安装和启动入口不变。没有执行历史 DOS 自动清理或多方法 Tc 数据迁移。

## 2026-10-16：US15 DOS 唯一值正式实现验证

- 独立候选从 HEAD 导出，只覆盖本次代码；property_evidence.py / upload_contracts.py 仅移植 DOS 增量，排除 #120 等已有未提交修改。候选目录：/var/folders/j8/21skwz6d3c1810rwvq3kpjf00000gn/T/scwiki-dos-candidate-t7e3wuyk。
- 独立候选前端 5 文件、96 项通过，包括 DOS 9 项；后端 4 文件、31 项通过，包括 DOS 9 项及真实 SQLite 保存／重读、拒绝新增第二条、空当前值拒绝、归档校验与模型不能独自确认矛盾。工作树的相同后端目录有另外两项其他任务的未提交测试，共 33 项通过；不将它们计入独立提交证据。
- TypeScript／生产构建在工作树和独立候选均通过。末次前端变更是有效人工确认提示及其过期回归，已在最终独立候选重新验证；日志 /tmp/scwiki-dos-candidate-ui-tests.log 与 /tmp/scwiki-dos-candidate-build.log。
- [正式组件浏览器记录](assets/dos-implemented-validation.json) 的 9 组断言通过；[宽屏截图](assets/dos-implemented.png)、[窄屏截图](assets/dos-implemented-mobile.png) 使用真实共享组件、纯后端生成的隔离快照及受控 API 夹具，不是旧独立 HTML Demo。390px 页面与侧栏不溢出，返回聚焦原始值且页面位置保持；只读无返回编辑入口，修改后人工理由即时可见。
- 浏览器可复核材料：[组件夹具入口](assets/dos-implemented-browser-harness.tsx)、[数据](assets/dos-implemented-fixtures.json)。入口复制到临时 Vite 根目录 main.tsx，数据复制为 dos-fixtures.json；src/node_modules 指向项目 frontend 同名目录。macOS 的临时目录逻辑路径和真实路径均需在 Vite fs.allow 中允许。仅表注来自已审计备份，19.10 明确为冲突演示值，不写真实草稿。
- 测试使用 SQLite 内存库与进程内测试 JWT；最初缺少 DATABASE_URL／JWT_SECRET_KEY 的环境错误在设置隔离测试值后消除，不修改系统配置。构建仍有既有 3Dmol eval／分包提示，组件旧夹具有 MUI 选项提示；未计作失败。
- 本轮没有业务数据库迁移、真实原任务 PUT、历史批量修复或远端部署／推送。旧重复正式记录由服务端拒绝隐式新增或删除，须明确处理；旧未提交草稿在转换与正常保存边界收敛，不执行全库扫描改写。#94 其他工作及远程链接门继续保持。

## 2026-10-16：结构优化选项文案修订

- 结构优化核处理的中文 classical_static 标签改为“经典静态优化”，英文改为 Classical static optimization；MaterialStatesEditor 与 PaperEditView 共用该字典，不改变保存值或后端契约。
- 与 HEAD 字典逐项比对：中英文均仅 structureOptimization.classical_static 的显示文字变化，其他键值一致。既有 enum-labels-i18n 6 项和 material-states-editor 27 项，共 33 项通过。
- 本机 Node 26 默认 Web Storage 使既有双语测试的 localStorage.clear 读取失败；使用命令级 NODE_OPTIONS="--no-experimental-webstorage" 后，两份测试全通过，不修改系统环境或测试源码。命令：NODE_OPTIONS="--no-experimental-webstorage" node "frontend/node_modules/vitest/vitest.mjs" run --config "vitest.config.ts" "tests/01_decentralized_uploading/material-states-editor.test.tsx" "tests/01_decentralized_uploading/enum-labels-i18n.test.tsx"。
- 纯文案修订不新增测试或执行数据库迁移；历史 Spec 的提案文字和原 Demo 保留，本次 FR-046 及最新修订为当前规则。未推送，Issue #94 保持开放。


## US18 正式简洁结构区验收

基于 HEAD 归档仅叠加本次组件、3行字典键及结构测试，路径 `/tmp/scwiki-structure-accepted`（临时验证目录）。运行：

```bash
NODE_OPTIONS=--no-experimental-webstorage node frontend/node_modules/vitest/vitest.mjs run --config vitest.config.ts tests/01_decentralized_uploading/structure-attachment-collapse.test.tsx tests/01_decentralized_uploading/structure-detail-collapse.test.tsx tests/01_decentralized_uploading/property-module-collapse.test.tsx tests/01_decentralized_uploading/material-states-editor.test.tsx tests/01_decentralized_uploading/crystal-structure.test.tsx tests/01_decentralized_uploading/paper-detail-route.test.tsx
```

6份58项通过；在 frontend 执行 `npm run build`，TypeScript 和 Vite 构建通过。真实浏览器经 CUA 打开隔离 Vite 夹具，使用正式 MaterialStatesEditor、PaperEditView、EvidenceFieldMarkers 及3Dmol；夹具将 fetch 全部截断，模拟数据不读写业务服务。

复现夹具：将 `assets/structure-collapse-implemented-harness.tsx` 复制至独立源码的 `frontend/structure-accepted.tsx`，把 `../../../../frontend/src/` 导入前缀替换为 `./src/`；建立含 root 节点及指向该脚本的独立HTML，再通过 Vite 打开。验证结果、截图及源码哈希见同目录 structure-collapse-demo.md 和 assets/structure-collapse-implemented-validation.json。

扩大检查中的旧只读字段测试2项在 HEAD 原组件复现，不计入通过数；共享工作区未提交的多 Tc 逻辑有2项相关测试失败，独立候选27项材料表单通过，未把其他任务修改纳入本次。没有执行推送、部署、真实业务保存或 AI 调用。


## US19 正式添加入口位置验收

独立源码目录`/tmp/scwiki-module-bottom-accepted`只含HEAD及本次PropertyModuleEditor的Select移动。验证命令：

```bash
NODE_OPTIONS=--no-experimental-webstorage node frontend/node_modules/vitest/vitest.mjs run --config vitest.config.ts tests/01_decentralized_uploading/property-module-collapse.test.tsx tests/01_decentralized_uploading/property-record-editor.test.tsx tests/01_decentralized_uploading/property-spectra-navigation.test.tsx tests/01_decentralized_uploading/material-states-editor.test.tsx
```

4份70项通过；frontend中`npm run build`的TypeScript/生产构建通过。真实共享组件的7组浏览器检查及390px无溢出见[module-add-bottom-demo.md](module-add-bottom-demo.md)正式验证段和assets/module-add-bottom-implemented-validation.json。模拟接口响应与组件夹具留档，不读写业务任务。

复现浏览器夹具：复制assets/module-add-bottom-implemented-harness.tsx到隔离源码frontend目录，将导入前缀`../../../../frontend/src/`改成`./src/`，用独立HTML挂载root并经Vite加载。两卡提供独立添加菜单，使用只读/无模块切换验证边界。构建和回归无需运行夹具。


## US20 正式共享表单验证

运行前端定向回归：`npm --prefix frontend run test:upload-ui -- tests/01_decentralized_uploading/calculation-field-settings.test.tsx tests/01_decentralized_uploading/predicted-tc-groups.test.tsx tests/01_decentralized_uploading/issue139-parameters.test.tsx`，并运行生产构建。测试涵盖取消/应用、非法范围、新增/删除/重开、外部修改拒绝、只读与具体Tc配置。

实际浏览器使用正式PropertyModuleEditor的隔离harness：assets/field-sidebar-implemented-harness.tsx，初始夹具field-sidebar-implemented-fixture.json，保存载荷field-sidebar-saved-browser-payload.json。页面保存为sessionStorage，不是业务HTTP保存；随后载荷送入test_tc_groups_mysql.py的field-sidebar参数用例，执行真实服务保存、返修和导出。不得用脚本夹具冒充真实原任务改写。

结果与截图见[正式实施记录](tc-field-sidebar-demo.md)，图片field-sidebar-implemented-wide/editor/mobile.png及验证JSON位于assets。浏览器检查17项、初轮相关前端59项和构建通过，MySQL与标注契约合计5项通过；最终以独立暂存候选结果为准。
