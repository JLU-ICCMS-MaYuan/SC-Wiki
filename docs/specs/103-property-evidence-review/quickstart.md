# 验证路径

## 结构附件紧凑与独立折叠（2026-09-17）

对应 FR-039/040、SC-026/027、T058—060，继续同一 Issue/Spec 的字段统一和左右结构方案。本轮不改后端、数据库、科学解析或保存接口。

- 新增 `structure-attachment-collapse.test.tsx` 两项，先复现缺少折叠入口，再验证独立折叠、模型节点不卸载、候选保留、收起仍可核对、无修改副作用、无结构及上传/新增候选自动展开。
- 7 个相关 Vitest 文件共 59 项通过：新增附件测试以及 `crystal-structure`、`scientific-layout`、`scientific-evidence-markers`、`upload-task-editor-layout`、`paper-detail-form-parity`、`admin-edit-page`。
- 新增 `structure-compact-browser.mjs`：真实上传组件和实际管理员编辑路由，接口全部隔离。1/64 原子时上传双栏各 539 × 400px，审核双栏各 513 × 400px，左右底边对齐；模型图例不存在。390/320px 窄屏模型 280px、数据区 400px，无页面横向溢出。
- Chromium 验证真实 3Dmol 非空像素、旋转/缩放、Enter/空格折叠、重开保持视角与画布像素、候选/晶胞/坐标选择不丢失、收起时来源核对可打开且关闭恢复焦点；全部查看操作无新增保存/核对失效请求。右侧内容在限定区域内滚动。
- 原 `scientific-layout-browser.mjs` 重跑通过：上传保存 → 提交 → 审核保存 → 详情重载的隔离接口往返，及多候选、晶胞、格式和坐标切换仍正常。
- `npm run build` 与 `git diff --check` 通过，保留既有 3Dmol eval、Vite CJS 与大包提示；桌面、折叠和手机截图已检查，无文字遮挡。
- 截图：`/tmp/scwiki-structure-compact/{upload,admin}-{desktop,collapsed,mobile-390,mobile-320}.png`。脚本支持 `ARTIFACT_DIR`、`FRONTEND_URL`、`PLAYWRIGHT_MODULE`、`CHROMIUM_PATH`。

```bash
node "tests/01_decentralized_uploading/structure-compact-browser.mjs"
node "tests/01_decentralized_uploading/scientific-layout-browser.mjs"
npm --prefix "frontend" run build
```

没有修改真实论文、调用 AI、执行批准或部署。此前真实数据库链路验收不作为本轮重新运行的结果；本轮纯前端变化通过隔离浏览器复查交互与保存往返。

开工基线为 `/tmp/scwiki-structure-compact-etYjrv/before.tar`。本轮独立补丁保存在 `/tmp/scwiki-compact-isolation-onby20/task-only.patch`，用只含 HEAD 的临时 index 执行 `git apply --cached --check` 失败：`CrystalStructureView.tsx` 在 HEAD/index 中不存在，两个已有结构组件和 Spec 区块均依赖前序未提交内容。不能把开工前已有的整个未跟踪文件当作本轮新增提交，因此未改真实暂存区、未提交，无本轮哈希。保留工作区，T060 提交部分继续未完成；不切分支、不推送。

## 正式统一布局与结构左右展示（2026-09-17）

本轮是正式组件实现，不是 Demo 接口验收。对应 FR-035—038、SC-023—025、T053—057。

- 7 个相关 Vitest 文件、63 项通过：材料关系来源保留/历史值/空值、结构精确绑定及未定位入口、多状态重排、共享编辑/详情/保存，以及真实 3Dmol 非正交 POSCAR 的分数与直角坐标。
- `test_scientific_layout.py` 3 项通过，其中 1 项使用当前 MySQL 外层事务回滚验证正式科学保存端点、重读、状态类型和材料汇总、关系来源保留；未修改真实论文、未执行迁移。
- `scientific-layout-browser.mjs` 使用真实上传/审核/详情组件及全部隔离接口，覆盖上传保存 → 提交 → 管理员保存 → 详情重载。验证 1440px 等宽两列、390/320px 上下布局、表格内部滚动、候选/晶胞/格式切换、非正交坐标、模型非空像素及旋转缩放、汇总定位和只读详情。
- `evidence-drawer-browser.mjs` 管理员与超级管理员均通过，核对完成关闭后保留滚动位置及焦点。
- `npm run build`（TypeScript/Vite）通过；保留已有大包体积提醒。
- 截图输出目录：`/tmp/scwiki-scientific-layout/`；浏览器脚本支持 `ARTIFACT_DIR` 覆盖，支持标准 `PLAYWRIGHT_MODULE`、`CHROMIUM_PATH`、`FRONTEND_URL`。

运行后端用例时使用项目 `sc-wiki` Python 环境；通过私有 `.env` 加载数据库连接（不打印连接信息），
设置进程内 `DEBUG=false`、测试专用 `JWT_SECRET_KEY` 与 `SCWIKI_CURRENT_MYSQL=1`。
浏览器接口往返与真实数据库事务分别验证；本轮没有运行真实论文的上传、AI 审核、批准或发布全链路，不能据此关闭整个 #103。

提交范围以开工快照 `/tmp/scwiki-layout-production-dZPNY5/before.tar` 为基线检查，不能把前序未提交模块整份纳入本轮。

独立提交检查未通过：本轮差量在当前 index 上无法应用于上传编辑、管理员编辑及多个已有未提交 Spec 区块；
`EvidenceFieldMarkers.tsx` 仍是开工前已存在的未跟踪文件。另在临时目录提取 HEAD 并仅加入可分离的结构组件，
全站构建仍因 HEAD 缺少前序 `evidenceFields`、`evidenceProposals`、`EvidenceFieldMarkers` 等模块失败。
当前完整工作树构建与上述测试通过，但不能把前序工作并入本轮提交来掩盖边界，因此本轮不暂存、不提交，T057 保留未勾选。

## 红框不遮挡文字（2026-09-16）

FR-034 / SC-022 / T052：旧共享标记在 MUI outlined 控件外叠加完整 outline，绕过原有 legend
缺口，边线穿过浮动标签。新增四类控件样式测试先全部复现，再改为原有缺口边框着红色。
标签沿用原有前景层，不靠白底、高全局层级或点击遮罩，普通区域红框不变。

```bash
node "frontend/node_modules/vitest/vitest.mjs" run --config "vitest.config.ts" \
  "tests/01_decentralized_uploading/scientific-evidence-markers.test.tsx" \
  "tests/01_decentralized_uploading/tc-record-layout.test.tsx" \
  "tests/01_decentralized_uploading/pressure-review-editing.test.tsx" \
  "tests/01_decentralized_uploading/evidence-drawer-close.test.tsx" \
  "tests/01_decentralized_uploading/evidence-workflow.test.tsx"
node "tests/01_decentralized_uploading/evidence-border-browser.mjs"
node "tests/01_decentralized_uploading/tc-record-browser.mjs"
npm --prefix "frontend" run build
```

浏览器使用现有 Vite；支持 FRONTEND_URL、PLAYWRIGHT_MODULE、CHROMIUM_PATH。
EVIDENCE_BORDER_SCREENSHOT 可指定截图前缀，自动保存浅色与深色截图。脚本加载真实共享生产
组件，隔离全部 API，不调用模型、不访问或改写真实论文。

- 69 项相关 Vitest 通过，包含 10 项标记测试及原压强/Tc/侧栏/工作流回归。
- Chromium 覆盖非白浅色与深色背景、960/360px 视口、中英文、数值/下拉/多行/空值聚焦/只读。
  检查真实边框样式、标签前景和缺口宽度；点击标签、键盘核对及数字编辑正常，解除标记不移动布局。
- TypeScript 与生产构建通过；既有 Vite CJS、3Dmol eval 和产物体积提示保留。
- 原 Tc 浏览器脚本在管理员、超级管理员及上传三条实际页面路径通过，包含输入、保存重载、
  人工理由失败重试、成功关闭和位置保持，截图确认紧凑 Tc 标签也保留缺口。
- 本次只改前端显示，不改变接口或数据库，不重复运行后端科学保存测试。

开工备份：/tmp/scwiki-evidence-border-baseline-C9oHX0。EvidenceFieldMarkers.tsx 及已有标记测试
仍属于前序未提交文件，当前 HEAD 中不存在，无法只暂存本轮几行增量形成独立完整提交。
沿用原提交隔离阻塞，保留工作树与空暂存区，不切换分支、不推送，也未执行生产部署。

## 完成自动关闭与页面位置（2026-09-16）

FR-033 / SC-021 / T050—051：此前代码只在核对项被删除时关闭，普通成功仍打开；关闭 300 毫秒后全页面查找同 key 的首个入口，实际命中顶部新增的已接受按钮，浏览器 scrollY 从约 2700 跳至 0，无额外页面导航。另有接受列表增高造成 56 像素位移。

现在当前组全部保存成功后统一关闭，失败保留输入。记录实际入口及字段位置，列表更新在绘制前抵消位移，关闭动画结束用 preventScroll 返回原字段；迟到请求不改变后来打开的侧栏。重新打开仍可查看理由和撤销接受。接口、数据库和批准流程未改。

- Vitest：`evidence-drawer-close` 5、`evidence-workflow` 23、`pressure-review-editing` 14、`material-name-review` 6、`scientific-evidence-markers` 6，合计 54 项通过；新回归先复现失败后通过。
- `npm run build` 通过，包含 `tsc -b`；仅有既有第三方 eval 和构建块大小警告。
- Chromium `evidence-drawer-browser.mjs` 使用实际管理员编辑页末尾材料状态，管理员/超级管理员均通过完成、遮罩、Escape、关闭按钮、返回修改。关闭前后字段视口位置相同，完成全程逐帧采样偏移不超过 3 像素，无新增导航；顶部列表增高也不造成可见抖动。
- 原 `pressure-review-browser.mjs`、`material-name-review-browser.mjs` 更新成功后自动关闭的预期并在两角色通过，含失败重试、删除与刷新恢复。全部 API 使用隔离夹具，零模型、零正式批准，不写真实 #29；本次为纯前端交互修复，未重复运行无变化的数据库回归。

提交隔离检查：开工备份 `/tmp/scwiki-drawer-baseline-Cj4klQ`，本轮增量 `/tmp/scwiki-drawer-only.patch`。仅含 HEAD 的临时 index 上 `git apply --cached --check` 失败：共享侧栏已有未提交的主体实现，相关浏览器与压强回归文件尚未进入 index。完整修复无法与前序依赖安全分离，依照 AGENTS.md 未暂存或提交、未切分支或推送；T051 文档已同步，提交部分保持未完成。

2026-09-16 材料名、空化学式与人工确认保存 500 的最新验收见 [保存闭环](material-name-save-flow.md)：31 项 Python、86 项不同前端回归、Go、构建及两角色 Chromium 验证通过；包含隔离方式、现有数据摘要和独立提交阻塞说明。

## 压强编辑与人工确认验收（2026-09-15，当前行为）

本节对应 FR-026—028 / SC-016—017；下方各日期记录是历史验收，不作为本次自动续提或真实论文写入授权。

- Chromium 使用实际 `/admin/papers/990103/edit` 页面，全部 `/api/**` 由内存夹具接管。管理员、超级管理员均通过：红框 0.000101 全选改为 0.0025、数字不打开抽屉、标签打开、返回聚焦、填写理由并完成、临时无效指数阻止保存、剪贴板粘贴零、整组清空、刷新后五字段仍空。每角色三次科学保存，零模型与批准请求，无意外 API 或页面错误。
- 浏览器回归真实发现原生监听器提前恢复旧值；微任务通知仍复现，改为完整事件传播结束后通知并排除失焦重复 change 后通过。组件测试未覆盖浏览器监听器之间的微任务行为，不能单独作为该问题完成证据。
- Python 专项六文件 45 项通过，包含新增压强 MySQL 回滚链路与上传规范化测试。新建隔离论文经生产科学保存函数修改、确认、清空，再用新会话读取；验证当前版本人工决定、保留旧判断、忽略旧接受、压强核对项移除和修改历史。外层事务最终全部回滚；不创建临时数据库、不修改 #29。
- Vitest 共 114 个不同用例通过：共享流程 23、标记 6、压强 14、队列 3、候选 2、材料编辑 25、上传性能 5、上传布局 22、管理员编辑 9、科学编辑 5。覆盖保存中继续编辑、迟到快照、失败重试、普通保存保留理由、反序编辑只失效对应项及旧候选隔离；完成或重新查找在等待期间切换论文，不会触发新论文保存。一次高并发运行的初始标签等待超过 1 秒，降低并行后专项通过；未修改断言绕过问题。
- Go handlers 通过；TypeScript 与 Vite 构建通过（保留既有 3Dmol eval 和大分包提示）。本次未重复跨 Go/Python 正式批准集成，完成按钮不负责批准。
- 扩大 Python 验证时，既有 `test_evidence_draft_version.py` 两项失败：仍替换旧 API 层的草稿函数，当前保存入口已委托 `save_completed_upload`，实际读取空草稿；测试还预期旧版本/缓存行为。本次没有修改该测试或该保存函数（与开工备份逐段对比一致），不将两项计入通过结果。

复跑核心路径（在仓库根目录，先加载已有 `.env`，不要打印凭据）：

```bash
DEBUG=false SCWIKI_CURRENT_MYSQL=1 /home/mayuan/miniconda3/envs/sc-wiki/bin/python -m pytest \
  "tests/01_decentralized_uploading/test_pressure_review_mysql.py" \
  "tests/01_decentralized_uploading/test_pressure_normalization.py" \
  "tests/01_decentralized_uploading/test_scientific_evidence_mysql.py" \
  "tests/01_decentralized_uploading/test_evidence_proposals.py" \
  "tests/01_decentralized_uploading/test_scientific_evidence.py" \
  "tests/01_decentralized_uploading/test_property_evidence.py" -q
"frontend/node_modules/.bin/vitest" run --config "vitest.config.ts" --maxWorkers=2 --minWorkers=1 \
  "tests/01_decentralized_uploading/pressure-review-editing.test.tsx" \
  "tests/01_decentralized_uploading/evidence-workflow.test.tsx" \
  "tests/01_decentralized_uploading/scientific-evidence-markers.test.tsx"
npm --prefix "frontend" run build
```

浏览器脚本为 `tests/01_decentralized_uploading/pressure-review-browser.mjs`，需要现有 Vite 与 Playwright/Chromium；可用 PLAYWRIGHT_MODULE、CHROMIUM_PATH 指定本机已有安装，FRONTEND_URL 默认为 `http://127.0.0.1:5173`。脚本拦截全部 API，不连接真实科学数据保存接口。

本次开工备份为 `/tmp/scwiki-pressure-baseline-g5N51l`，独立补丁为 `/tmp/scwiki-pressure-only.patch`。临时 Git index 读取 HEAD 后执行 `git apply --cached --check`，结果不能应用：此前未提交的 evidenceFields、evidenceDraftQueue、EvidenceFieldMarkers、scientific_evidence、evidence_proposals 等不在 index，工作流与编辑页又有同块重叠。无法仅提交本次变更形成完整版本；遵循仓库禁止混入既有修改的规则，未暂存、提交、切分支或推送，T043 保留提交阻塞。

使用现有 sc-wiki 环境；增量 Alembic 迁移，不建立临时数据库。#29 通过真实队列核对，禁止改写科学值；写入使用外层回滚事务，发布副作用由本地测试端承接。浏览器验证上传者、管理员、超级管理员的取消、自动续提、疑点裁决、手动原文和错误提示。运行针对性 Python/Go/Vitest 测试与前端构建；结果须记录于本文件，未完成不得宣称通过。

## 环境与运行方式

2026-09-11 在现有 sc-wiki MySQL、Redis/RQ、本地 Python 8000、Go 8080、Vite 5173 验证。
Alembic 已应用 `20260911_0103`。该迁移只新增核对表，未批量修改历史论文。

从仓库根目录加载当前环境后运行 Python 回归，数据库必须为当前 MySQL：

```bash
set -a
. "./.env"
set +a
SCWIKI_CURRENT_MYSQL=1 PYTHONPATH=. /home/mayuan/miniconda3/envs/sc-wiki/bin/python -m pytest \
  "tests/01_decentralized_uploading/test_property_evidence.py" \
  "tests/01_decentralized_uploading/test_property_evidence_mysql.py" -q
```

前端针对性回归和构建：

```bash
/home/mayuan/.volta/bin/npm --prefix "frontend" run test:upload-ui -- \
  "tests/01_decentralized_uploading/evidence-workflow.test.tsx" \
  "tests/01_decentralized_uploading/property-record-editor.test.tsx" \
  "tests/01_decentralized_uploading/admin-paper-classification-review.test.tsx" \
  "tests/01_decentralized_uploading/upload-task-editor-classification.test.tsx"
/home/mayuan/.volta/bin/npm --prefix "frontend" run build
```

Go 真实审核回归使用已完成的 #29 核对任务。先通过当前管理员的共享核对界面或接口取得任务 id 与
预检查 version，分别设置 `SCWIKI_EVIDENCE_JOB_ID`、`SCWIKI_EVIDENCE_VERSION`；
`SCWIKI_EVIDENCE_ACTOR_ROLE` 设置为创建任务的 admin 或 superadmin。
`SCWIKI_TEST_MYSQL_DSN` 从当前 DATABASE_URL 转换到 Go DSN，在进程环境中传递，不打印凭据。

```bash
SCWIKI_CURRENT_MYSQL=1 /home/mayuan/.local/go/bin/go -C "goserver" test ./handlers \
  -run 'TestCurrentMySQL(EvidenceReview|QuickReview)$' -count=1 -v
```

`TestCurrentMySQLEvidenceReview` 对现有 MySQL 开启外层事务，真实转发 Python prepare-review，
仅将事务外发布与清理请求交给测试服务器承接，退出时回滚。不要直接批准 #29 来代替回滚验收。

## 本次验证结果

| 验证层 | 结果与覆盖 |
| --- | --- |
| Python | 13 项通过；同页多片段、旧编号重新定位、伪引句、具体定位错误、页码传播、语义疑点、版本与禁止绕过 |
| 当前 MySQL 上传事务 | 原始 #29 草稿经真实 `_create_pending_paper` 保存、重载；跨状态相同局部键，多证据关联数为 2/1，核对缓存可复用；全部回滚 |
| 前端 | 34 项通过；3 秒取消、成功只续提一次、上传疑点、审核逐条理由、无出处、服务失败、卸载、迟到响应、缓存身份；原分类、三状态及记录编辑回归 |
| Go 当前 MySQL | admin 与 superadmin 均完成真实任务结果 → 疑点暂停 → 旧版本拒绝 → 人工理由批准 → Evidence 完整 → 幂等重试 → 历史留痕，原科学值不变；三状态回归通过；全部回滚 |
| 导出约束 | 在同一 MySQL 回滚事务内，人工批准后各材料状态可导出；移除一条记录证据后返回 `409 export_incomplete`，再回滚保存点 |
| 构建 | TypeScript 与 Vite 生产构建通过；现有 3Dmol eval 与大分包警告未造成构建失败 |

真实模型核对 #29 的多轮结果一致识别 Pb 与 SnHg 的主要科学疑点：

- SnHg 4.29 K 来自阈值电流测量温度，原文为该温度下阈值电流 0.12 A，不支持精确 Tc=4.29 K；模型还指出固定 SnHg 化学计量缺少依据。
- Pb 7.19 K 与原文“约 6 K”不符，显示具体数值冲突，不自动改值。
- Sn 3.78 K 的转变温度有原文支持；不同核对轮次可因压力或结构来源不足判 uncertain，审核流程按实际结果逐条展示，不把模型结论当作固定真值。

## 真实页面验收

使用真实 Chromium 页面及现有服务验证：管理员编辑页的 3 秒倒计时取消未创建模型任务；
超级管理员编辑页展示 #29 的 Pb/SnHg 原文与疑点，理由未齐全时不能人工批准。

普通上传者使用 #29 原文的验收任务，后台采用当前 MySQL 的外层回滚事务承接真实保存和提交端点，
模型仍通过真实 Redis/RQ 和用户配置调用。第一次倒计时内取消，模型任务和提交请求均为零；再次提交
只创建一个核对任务并只提交一次，页面跳转到测试论文详情。测试服务随后正常退出并回滚，清理验收任务、
Markdown 和提交快照。正式 #29 仍为 pending、revision=1，三个原值仍为 3.78、7.19、4.29 K。

手动来源及无出处、超时/服务错误、卸载等边界由共享组件与定位契约回归覆盖；没有声称模型在所有论文中均能找全或准确理解证据。
历史片段没有页码时显示片段编号，本次未扫描回填。

## 后续反馈修正验收：自动选择来源

用户明确取消手动证据选择后，共享组件移除片段选择器、引句编辑及内部文件/片段编号。原文默认折叠，
只有科学疑点仍需逐条理由；缺页码改为显示“原文未提供页码”。原接口 candidates 保留兼容，当前界面不发送。

本轮前端 27 项通过（共享流程 14 项、两工作台三状态 13 项），包括无手动选择控件、只读折叠原文、上传缺来源
不要求手动选证据、重试绕过旧疑点缓存后自动续提，以及重试倒计时取消。Python 13 项通过，仍使用现有
sc-wiki MySQL 外层事务回滚；TypeScript/Vite 生产构建通过。

真实 Chromium 打开论文 #29 管理员编辑页，使用当前后台和已有真实模型核对结果：无来源选择器，原文默认折叠且可展开，
没有内部编号，仅保留人工科学裁决输入框；点击重新查找进入三秒倒计时，取消后新增模型任务与批准请求均为零。
本轮未批准或修改正式论文。此前完整真实模型上传与审核验收保留为上一阶段记录，不将其等同于本轮新增验证。

上传疑点返回编辑页时，已完成任务会自动调用 `save-draft` 保存已找到的证据到 Redis；下次预检查复用该任务，
不会因点击“返回修改记录”再次调用模型。缺失出处仍不会写入虚假证据，正式提交时才随事务写入 MySQL。

## 模型格式错误验收

日志确认一次失败任务 `ef19ef5d…` 的根因是流式模型响应 JSON 截断（`JSONDecodeError`），不是表单或数据库。
现已对格式错误自动重试一次，新增 `backend/tests/test_llm.py` 回归；重试仍失败时使用 `evidence_model_format` 明确提示。

上传疑点返回编辑页时，已完成任务会自动调用 `save-draft` 保存已找到的证据到 Redis；下次预检查直接复用，
不会因点击“返回修改记录”再次调用 LLM。缺失出处不会写入虚假证据，正式提交时才随事务写入 MySQL。

## 后台核对进度反馈验收

共享组件在排队和执行中显示进度条，运行时使用后台实际原文分组计数；当前组、完成百分比和独立等待时间
同时可见。未知总量只显示动态等待，不按耗时虚增百分比。

本轮共享前端回归 16 项、Python 来源与任务契约回归 12 项通过，生产构建通过。新增回归验证排队时无虚假
百分比、等待计时、0/2 → 1/2 的 50% 推进、完成后自动续提及取消清理；后台回归从真实 Worker 入口执行
分组与结果处理，校验只有模型响应完成后才递增，并验证查询接口公开计数。

真实 Chromium 在现有 sc-wiki 环境的 #29 发起重新核对，使用真实 Redis/RQ 和模型服务，已观察排队 →
核对第 1/2 组（0%）→ 核对第 2/2 组（50%）→ 完成（2/2），页面截图确认进度条和等待时间可见；没有提交批准请求。

## 2026-09-15 扩展验收矩阵

本轮使用当前 MySQL 外层回滚事务，没有创建临时数据库，也没有实际批准论文 #29。

| 边界 | 本轮结果 |
| --- | --- |
| Python | 29 项通过：定位、#29 Tc 混淆、全科学项、missing 与理由持久化、按审核员隔离、局部失效、单位派生复核、上传转接、Redis 丢失恢复、显式清理与结构来源 |
| 后台检查点 | 模型第二组失败后，前八个 missing 结果及建议仍在真实 MySQL，新会话可读；关键存储没有替身 |
| Go | 全 handlers 通过；新增 Go → Python → 当前 MySQL 测试通过，覆盖无理由/旧版本拒绝、逐条裁决、来源保存、成功清理、幂等与失败回滚保留临时项 |
| 前端 | 六个测试文件共 68 项通过：共享工作流、稳定身份定位、排序/补证不误失效、两个工作台与上传编辑回归；生产构建通过 |
| 真实模型与 RQ | 对当前 #29 的物性项 61 定向重查，完整读取两组原文，任务完成并保存 uncertain 与五条可定位证据；删除本次任务的 Redis 结果/索引缓存后，预检查仍从 MySQL 恢复相同理由，没有再次调用模型 |
| 真实浏览器 | 上传校对、管理员与超级管理员编辑页，以及两个工作台快速审核，共享科学视图和右侧覆盖抽屉；验证关闭重开、刷新恢复、默认折叠原文、Escape 焦点返回、三秒重查取消后保留标记 |
| 来源与 RAG | 当前 #29 实际结构内容经解析后保存首次认证提交者，后续保存者不能覆盖；来源未知不能人工放行；正式来源转 RAG 内容及引用保留来源类型、提供者和论文未支持限定 |

浏览器疑点由测试服务在现有 MySQL 的回滚事务内构造确定性模型判断，真实页面、权限、持久结果读取与抽屉交互均执行。测试服务结束已回滚并清理自己的 Redis 任务及原文副本。真实 LLM/RQ 验证单独执行，不把判断替身算作模型验证，也未通过浏览器真实批准 #29。实际截图保存在本次环境 `/tmp/scwiki-103-admin-drawer.png`、`/tmp/scwiki-103-superadmin-drawer.png`、`/tmp/scwiki-103-user-drawer.png`。

全量 #29 核对曾完成首组后被验收流程取消；本轮真实模型完成证明限定为上述定向项。Qdrant 的来源类型与限定由发布、检索代码和来源契约测试验证，没有执行实际批准发布来改写现有向量索引。扩大运行的旧上传生命周期测试仍有旧表结构和替身签名不匹配问题，未纳入本轮专项通过数量。

### 专项运行

在项目 Python 环境加载现有连接配置后运行：

```bash
SCWIKI_CURRENT_MYSQL=1 python -m pytest tests/01_decentralized_uploading/test_property_evidence.py tests/01_decentralized_uploading/test_scientific_evidence.py tests/01_decentralized_uploading/test_scientific_evidence_mysql.py tests/01_decentralized_uploading/test_property_evidence_mysql.py -q
```

Go 跨服务测试为 `TestCurrentMySQLScientificEvidenceTransaction`，要求 `SCWIKI_CURRENT_MYSQL=1`、`SCWIKI_TEST_PYTHON` 和 `SCWIKI_TEST_MYSQL_DSN`，沿用现有 `DATABASE_URL/JWT_SECRET_KEY`。它启动 `scientific_review_bridge.py`，使用既有论文 #9 的分类和原文，所有批准写入由外层事务回滚；模型判断固定，事务外发布仅送本地接收器。不要与持有科学核对表写锁的浏览器回滚夹具并发运行。

前端从 frontend 执行 `npm run test:upload-ui -- <测试路径>` 和 `npm run build`，测试文件包括 evidence-workflow、scientific-evidence-markers、admin-paper-classification-review、admin-edit-page、upload-task-editor-layout 和 upload-task-editor-classification。Go 常规回归为 goserver 下 `go test ./handlers`。

### 文档与提交边界

Spec、Plan、Research、数据模型、接口、Tasks、Overview 和根 README 已同步新规则。迁移终点为 `20260915_0104`，运行环境已应用新增表；Go 和前端仍需按部署流程配套发布，不能把开发页面与源码验证当成已发布版本。

本轮与开始时已有未提交修改在五个文件同一区块交叠：backend/api/evidence.py、backend/ingest/property_evidence.py、frontend/src/components/EvidenceWorkflow.tsx、frontend/src/components/UploadTaskEditor.tsx、tests/01_decentralized_uploading/evidence-workflow.test.tsx。按初始备份生成独立补丁并用临时 Git index 检查，无法直接应用到 HEAD；单独提交其余文件会留下依赖不完整的提交。依照用户的范围隔离要求，未暂存或提交，没有创建/切换分支或推送。Issue 保持开放记录这一交付阻塞。

## 红点与建议验收（待执行）

分别验证上传、管理员/超管编辑及快速审核：同框多问题一红点、抽屉顺序、键盘返回、保存/恢复建议、接受/撤销、仅存疑理由、独立按钮布局。断言核对结束不提交、提交失效结果不调模型。使用现有 MySQL 回滚覆盖草稿、最终值绑定、权限、并发与事务失败；保留 #29 Tc 回归，不实际批准。运行针对性 pytest、Go、Vitest 和前端构建；记录真实浏览器证据后才勾选新任务。

## 本轮红点与建议验收结果（2026-09-15）

- Python：原来源、全科学核对、建议与真实 MySQL 回滚共 37 项通过；另 1 项用论文 #29 当前表单定义验证建议域约束通过（总计 38 个不同用例）。包括候选引句定位、冲突值不任选、缺来源禁止接受、人工理由、按用户恢复、撤销、迟到结果、同版本幂等、两段失败恢复及并发来源变更。
- Vitest：建议应用、标记、工作流、快速审核及编辑页 5 文件 49 项通过；上传布局、分类及错误处理 3 文件 27 项通过（共 76 个不同用例）。后续针对修改过的共享界面进行了同组回归。
- Go：handlers 全组通过；新增准备校验 HTTP 契约和人工决定序列化测试；真实 Go → Python → 现有 MySQL 批准/失败/重复事务测试通过，最外层全部回滚，发布端点仅本地接收器。
- 前端 production build 通过。真实 Chromium 验收 admin/superadmin/upload：单红点、无三角形、覆盖抽屉及内容顺序、编辑、完成、刷新恢复、撤销、键盘焦点与顶部边界；两个快速审核入口同样通过。页面 #29 的科学保存和批准被拦截；全程未发起模型或真实批准请求。建议语义使用明确测试替身，来源定位、认证、MySQL 草稿写入与恢复走真实代码。
- 浏览器临时服务器的数据库事务已回滚，临时上传 Redis 状态和文件已清理。未创建临时数据库，未实际批准论文 #29；本轮未声称实测新的线上 LLM 建议质量。
- 运行环境的 Vite、Python 和 Go 由既有热重载加载工作树；功能领先于 Git，不能据此关闭 Issue。
- 日志：`/tmp/scwiki-103-ui-python-final.log`、`/tmp/scwiki-103-ui-domain-test.log`、`/tmp/scwiki-103-ui-vitest.log`、`/tmp/scwiki-103-ui-upload-tests.log`、`/tmp/scwiki-103-ui-go-final.log`、`/tmp/scwiki-103-ui-go-mysql.log`、`/tmp/scwiki-103-ui-browser-final.log`。页面截图位于 `/tmp/scwiki-103-ui-{admin,superadmin,upload}-drawer.png` 与管理员 page.png。

提交隔离：本轮开工快照在 `/tmp/scwiki-103-ui-baseline/`，独立补丁与诊断在 `/tmp/scwiki-103-ui-only.patch`、`/tmp/scwiki-103-ui-isolation.log`。临时 index 上无法将本轮独立补丁应用到 HEAD：前序尚未提交的科学核对模块不存在于 index，且共享接口与组件的修改区块重叠。未修改真实暂存区、未提交、未切换分支或推送；T024、T031 的提交收尾仍阻塞。

## 说明文字入口验收（2026-09-15）

T032：6 项标记回归与 22 项共享工作流回归通过；TypeScript 与生产构建通过。新增真实 MUI 用例覆盖中英文标签、聚合、Enter/空格、输入框读屏名称、选择框、区域标题、解决后恢复标签与快速审核文字入口。Chromium 以实际共享组件和 MUI 控件运行隔离页面，验证点击、键盘、按现有工作流策略恢复焦点、选择框不误开、解决后标签默认聚焦及输入区域尺寸不变。浏览器夹具在 `/tmp/scwiki-103-label-browser.mjs`，截图 `/tmp/scwiki-103-label-page.png`；未重跑完整管理员/上传后端流程，不调用模型、不写数据库。原 T024/T031 提交阻塞保留。

## 人工确认与即时保存验收（2026-09-15）

当前 MySQL 上复现旧未核对保存 409 后增加回归；未核对草稿、无直接原文人工确认、空理由、上传越权、自审、版本变化、定点数 JSON 与 canonical 比较、RAG 人工归因均通过针对性测试。真实 Go → Python → 当前 MySQL 分别验证原文裁决和无引句人工裁决，批准、永久来源、历史、幂等及失败回滚通过；测试使用论文 #9 外层回滚，不实际批准 #29、不创建临时数据库。

真实 Chromium 加载当前共享表单/抽屉与实际 Python API，以新建论文的当前 MySQL 外层回滚验证连续输入只发一次保存、一次 503 后不自动重复、显式重试保存最新输入、刷新恢复、完成、finalize 及提交门禁。无模型或真实批准请求；脚本 `/tmp/scwiki-103-human-browser.mjs`，截图 `/tmp/scwiki-103-human-browser-accepted.png`，服务器已退出且回滚。

#29 使用现有服务端默认 gpt-5.6-sol，任务 cd865e67520c4d4681ff6ae4b7f66515 完成 8/8 批，复用原八项并补齐剩余 26 项。当前 34/34 有版本匹配结果，0 项 unchecked，2 supported、19 uncertain、6 unsupported、7 missing。超级管理员原六条接受草稿仍可恢复；论文保持 pending、revision=1，未改科学值或批准。存疑/无出处不等于任务未完成；现在可逐条给出人工理由确认。

最终验证：42 项 Python（包含现有 MySQL 外层回滚）、77 项 Vitest（七文件）、Go handlers 全组、两套真实 Go/Python/MySQL 回滚批准路径及 TypeScript/Vite 构建通过。提交隔离诊断见 `/tmp/scwiki-103-human-isolation.log`；本轮独立补丁 `/tmp/scwiki-103-human-only.patch` 不能应用到 HEAD，保留前序修改和 T024/T031/T037 提交阻塞，不动真实暂存区。

## 2026-09-17 整合复验与分批提交

用户授权核验并提交 #100 至 #106，另明确同意将 #103 必需的 Tc 依赖单独提交。此前各轮
“仅提交本轮差量”的隔离失败属于历史记录；本轮按依赖顺序收齐 #103，不再遗漏未跟踪组件、
后端服务及迁移。`backend/data/form_definitions.v1.json` 与
`alembic/versions/20260914_0052_custom_module_definitions.py` 仍保留在工作区，不纳入提交。

| 验证范围 | 本轮结果与边界 |
| --- | --- |
| 前端完整回归 | 工作树和排除无关改动的候选树均为 49 文件、396 项通过；涵盖三状态审核、侧栏、元素数缓存、晶系未知联动、社区与共享科学表单 |
| Python 专项 | 152 项通过、27 项因专用数据库门禁跳过；包括 Tc 的 9 份浏览器真实请求经 SQLite 生产持久化及导出重载；RAG 检索及发布另有 4 项通过 |
| Go | 排除无关改动的候选树执行 `go test ./...` 全部通过；未启用当前 MySQL 集成门禁 |
| 前端构建 | 候选树 TypeScript 与 Vite 生产构建通过，既有 3Dmol eval、产物体积及依赖弃用告警保留 |
| 结构浏览器 | 上传和审核均覆盖 1/64 原子、两栏 400px、窄屏模型 280px、无重复图例、多结构切换、键盘折叠与视角保留；画布像素检查和旋转通过，320/390px 无页面横向溢出 |
| 三视图保存 | 隔离 API 验证上传保存、提交、管理员编辑保存、详情重载；长关系来源保留，材料汇总与状态类型同步，详情只读 |
| Tc 与晶系 | 上传、管理员和超级管理员浏览器均通过 Tc 保存及重载；晶系重复选择未知、键盘、保存失败重试及重载通过 |
| 核对面板 | 两管理员角色关闭面板后保留滚动和触发位置，无页面错误；未调用真实模型或批准接口 |
| 迁移与文档 | 候选树 `alembic heads` 能完整解析至 `20260917_0107`；只读检查，未执行迁移。文档相对链接与 `git diff --check` 通过 |

回归修正保留原业务断言：批准前保存失败不得批准、已保存分类才进入审核请求、前端校验失败
不得提交、后端错误展开所属材料、结构上传仅一次、Tc 以当前值保存。补证测试按当前契约验证
“补证不改变科学断言版本、并发改值不能被旧证据覆盖”，不再模拟旧 Redis 版本推进。
RAG 复验使用内存 SQLite 验证待审和旧版本科学来源被过滤，发布仍保留真实块 ID 和来源限定。

运行记录位于 `/tmp/scwiki-delivery-{vitest,python,go,build}.log`、
`/tmp/scwiki-audit-rag-final.log`。结构截图在 `/tmp/scwiki-structure-compact/`，
三视图截图在 `/tmp/scwiki-scientific-layout/`。本轮没有重新验证真实 LLM 输出质量、没有改写真实
论文或部署数据库；此前 MySQL 回滚验收仍按原记录的时间和范围引用，不充当本轮重跑结果。
应用级交付由 Tc 依赖批次及后续 #103 整合批次共同组成，不把中间依赖提交视为独立完整应用。
未切换分支、未推送或关闭 GitHub Issue；本地交付不等于远程发布。
