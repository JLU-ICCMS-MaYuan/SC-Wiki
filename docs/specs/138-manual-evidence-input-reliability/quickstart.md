# 验收路径：人工证据输入与编辑可靠性

**Issue**：[#138](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/138)；**日期**：2026-10-15。

初版为规划文档；现已按用户“开始落地”实施，结果与边界见末尾记录。

## 前置条件

1. 实施前重新读取 Spec、Plan、Research、数据模型、契约、Tasks 和 #109 US8 当前状态；确认代码实施授权及 mayuan 分支，保护其他任务的未提交修改。
2. 使用隔离测试环境与可追溯的前端/Go/Python 制品；准备测试上传草稿、返修草稿及有权编辑的管理员、超级管理员账号。不得将隔离环境结果称为用户当前站点已修复。
3. 使用现有迁移与人工证据存储；准备无敏感内容的 PNG/JPEG/WebP、UTF-8 TXT/MD、有效 PDF，以及空、伪造类型、超 10 MiB、满五项样本。无需新增数据库迁移。
4. 准备 Chrome 与 Safari、系统截图剪贴板；开发者工具保留网络与控制台记录。核对构建/进程来源，区分开发热更新和产品行为。

## 自动回归命令（实施后执行）

在仓库根目录使用已配置的 Python 环境执行：

```sh
node "frontend/node_modules/vitest/vitest.mjs" run --config "vitest.config.ts" "tests/01_decentralized_uploading/manual-evidence-section.test.tsx" "tests/01_decentralized_uploading/manual-evidence-drafts.test.tsx" "tests/01_decentralized_uploading/manual-evidence-editor.test.tsx"
python -m pytest "tests/01_decentralized_uploading/test_issue109_manual_api.py" "tests/01_decentralized_uploading/test_issue109_manual_evidence.py"
npm --prefix "frontend" run build
```

两个前端测试文件已由实施任务创建并运行，结果见末尾记录。失败时保留原始输出及失败层级，不通过删测试或修改约束声称完成。

## 浏览器与真实存储矩阵

| 场景 | 操作 | 预期结果 | 覆盖 |
|---|---|---|---|
| 点击与拖入支持类型 | 各类型通过点击和拖拽添加、上传、预览并删除 | 同一校验及人工来源，无导航或刷新 | US3 / FR-001、003—004 / SC-001、005 |
| 系统截图粘贴 | 系统截图到剪贴板，焦点在证据区后 Cmd/Ctrl+V | 无本地保存即可预览/上传，文件名与真实类型一致 | US3 / FR-002 / SC-001、005 |
| 普通文字粘贴 | 在理由/主表单文本框粘贴文字；证据区粘贴无图片内容 | 文本框正常；证据区不造空图或直接文字证据 | US3 / FR-004 / SC-005 |
| 文件异常 | 空文件、伪造类型、超限、已有五项后再加入 | 明确错误，原有输入与合法证据保留 | US3 / FR-003、008 / SC-001、004 |
| 立即打开 | 实际改值后在五秒自动保存前点击字段名 | 当前修改入口立即呈现或明确待同步，无需刷新，不调用模型 | US2 / FR-005 / SC-002 |
| 保存后打开及改回原值 | 等自动保存/显式保存后打开；再改回原值 | 入口与服务端变化判定一致，历史可读 | US2 / FR-005、010 / SC-002、005 |
| 多字段理由与待上传文件 | 两字段分别输入不同理由/缺证原因、选择/粘贴文件，切换选项与字段，关闭重开 | 最新内容仍在原字段，待上传状态不伪报成功 | US1 / FR-006、009 / SC-003—004 |
| 后台与迟到响应 | 控制读取响应延迟；期间继续输入，模拟其他字段改变整体版本 | 新输入不被覆盖，旧响应不影响新字段或任务 | US1 / FR-006、008 / SC-003—004 |
| 主值、说明、文件分阶段失败 | 分别注入主表单校验/保存失败、PUT 失败、文件失败和 409 | 保留输入，指明阶段；部分成功真实显示，显式重试成功项不重传 | US1、US2 / FR-008—009 / SC-004 |
| 提供证据与选择器返回 | 多字段填入后反复切换选项、打开/取消文件选择器、切回页面 | 无意外 Document 导航、路由重建或输入覆盖；记录真实触发边界 | US1、US3 / FR-007 / SC-003、005 |
| 保存刷新重开 | 成功保存说明和上传证据后刷新，并从服务器重读 | 归属、值版本、文件内容一致；未上传项不称已持久化 | US1 / FR-009—010 / SC-004—005 |
| 权限与历史 | 测试无权访问、删除已提交/他人项、改值后查看旧证据 | 既有服务端限制仍有效；历史只读，旧证据不为新值背书 | 全故事 / FR-010 / SC-005 |
| 四入口与可访问性 | 上传、返修、管理员和超级管理员；键盘聚焦、中文/英文、桌面/390px | 共享行为一致、焦点可用、无横向页面溢出，不自动提交/批准 | 全故事 / FR-010 / SC-005 |

## 整页刷新根因记录要求

记录操作步骤、时间、浏览器版本、运行制品/源码版本、Document 请求与路由变化、组件挂载和异常信息。若只有组件状态覆盖，应写清并附时序；若真实导航出现，应定位发起者。不能以组件测试未发现刷新判定用户所见不存在。

## 真实存储验证

在隔离数据库与现有文件存储下完成添加说明、文件上传、鉴权预览、刷新重读、返修/提交转接及历史读取，核对字段、版本、提交者、文件哈希与大小。区分已保存说明、已上传文件和尚在会话内的 File。若测试 MySQL 或文件后端不可用，明确保留未验收项。

## 证据与完成判定

每次执行记录命令、环境、源码/构建身份、样本、实际结果及证据路径。SC-001—005 都有对应矩阵结果后才能判功能验收通过；Overview、README、远程链接与 Issue 关闭检查另行完成。

目前状态：本地实现及定向验证已完成；真实环境和完整验收缺口以末尾记录为准，不能把本地通过等同于全部验收通过。

## 2026-10-15 本地实施与验证记录

用户已明确授权“开始落地”。生产组件已经接入，以下是实际验证范围；前文矩阵仍作为完整验收清单，未覆盖项不算通过。

### 已执行

- Node v24.19.0、Vitest v2.1.9：三份人工证据测试加 evidence-workflow、evidence-drawer-close、evidence-draft-queue，合计 63 项通过。覆盖即时入口、主值失败不写说明、字段/值隔离、侧栏重开、旧读取/写入响应、部分上传失败、未上传文件保护、大小/数量边界、图片粘贴、预览释放和新字段身份归并。
- 前端 TypeScript/Vite 生产构建通过（现有大分包提示保留）。提交前还使用仅含本次暂存修改的独立副本复验，结果见本节补充。
- Python 3.12 的既有人工证据 API/服务测试共 18 项通过；使用进程内测试 JWT、隔离 SQLite 和临时文件，不接触业务库，覆盖版本拒绝、图片/PDF 真实字节存储、鉴权预览、历史与证据规则。
- Chrome 155.0.8059.40 的真实上传、返修、管理员与超级管理员页面全部通过。标题修改后立即补证，原生 ClipboardItem + Cmd+V 图片粘贴、PDF 拖入、系统文件选择器取消返回、多字段理由/文件保留、先保存主值再写说明/文件、保存后刷新重读均通过；未发生意外导航。1440px 桌面与 390px 窄屏的页面和侧栏均无横向溢出。
- 浏览器脚本为 [manual-evidence-browser.mjs](../../../tests/01_decentralized_uploading/manual-evidence-browser.mjs)，全部业务接口被隔离测试路由拦截，浏览器结果不证明真实 MySQL 的四入口端到端事务。截图为本机临时 QA 产物，位于 `/tmp/scwiki-138-browser/`，不作为永久归档附件。

### 可复跑命令

在仓库根目录，使用 Node 24 或其他已验证兼容的 Node 执行；系统 Node 26 的实验性 localStorage 会影响旧测试的 jsdom 全局对象，未为此修改业务代码或测试配置。

```sh
node "frontend/node_modules/vitest/vitest.mjs" run --config "vitest.config.ts" "tests/01_decentralized_uploading/manual-evidence-section.test.tsx" "tests/01_decentralized_uploading/manual-evidence-drafts.test.tsx" "tests/01_decentralized_uploading/manual-evidence-editor.test.tsx" "tests/01_decentralized_uploading/evidence-workflow.test.tsx" "tests/01_decentralized_uploading/evidence-drawer-close.test.tsx" "tests/01_decentralized_uploading/evidence-draft-queue.test.tsx"
JWT_SECRET_KEY="scwiki-138-isolated-test-secret" FILE_STORAGE_BACKEND="local" python -m pytest "tests/01_decentralized_uploading/test_issue109_manual_api.py" "tests/01_decentralized_uploading/test_issue109_manual_evidence.py" -q
npm --prefix "frontend" run build
PLAYWRIGHT_MODULE="/absolute/path/to/playwright/index.mjs" CHROMIUM_PATH="/absolute/path/to/chrome" ARTIFACT_DIR="/tmp/scwiki-138-browser" node "tests/01_decentralized_uploading/manual-evidence-browser.mjs"
```

PLAYWRIGHT_MODULE、CHROMIUM_PATH 是测试运行时路径，不是项目新增依赖或用户产品配置。浏览器脚本默认指向本地 Vite，所有 API 都被测试隔离。

### 扩展回归与边界

扩展到整个 `tests/01_decentralized_uploading/` 的一次回归得到 300 项通过、16 项失败（该次运行在随后补充的两项针对性测试之前）。16 项全部来自 pressure-review-editing 和 submit-validation-feedback；在独立副本撤除本次工作流、侧栏、语言及上传编辑器改动，同时保留其他任务原有改动后，两个文件仍是相同 16 项失败、7 项通过。失败类别为重复压强标签和多 Alert 断言，不能报告全目录测试全绿。

Safari、真正系统截图快捷键写入剪贴板的路径、真实 MySQL 下完整上传→返修→批准与权限事务仍待验收。当前实现已在 Chrome 原生剪贴板路径与真实服务端隔离文件测试通过，不将两者合并声称生产链已全部验收。未推送、未执行迁移或部署，Issue 保持开放。

### 仅含本次暂存改动的独立副本验证

从 Git 暂存区导出独立副本，不带其他任务的未提交改动。TypeScript/Vite 构建通过；第一次全目录回归 303 项通过、11 项失败，仅余已在任务前副本确认的压强重复标签用例；其他任务工作区中的 5 项多 Alert 失败未进入本提交。后续补入物性条件身份回归后，最终定向回归为 63 项通过。不宣称全目录全绿。

## 2026-10-15 用户完成确认与关闭

用户明确表示：“这个需求完成了。可以关闭这个 issue 了”。据此以当前交付范围完成本需求并关闭 #138，不再以此前列出的补充环境验证阻止本次关闭。

既有 63 项定向回归、18 项后端测试和 Chrome 四入口验证记录不变。Safari、真实 MySQL 完整事务以及远程 Spec 链接未新增验证，不补勾为通过。本次重新查询远程 mayuan 的 Spec 仍为 HTTP 404；不推送、不部署。上传/审核 Overview 与 README 已在实现提交中更新，本次只记录用户确认与关闭依据。
