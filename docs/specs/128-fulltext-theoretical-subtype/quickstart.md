# 验收记录

## 前置条件与复跑命令

以下命令从仓库根目录执行。Python 使用项目 `sc-wiki` Conda 环境，前端已安装本仓库依赖；模型实测还需要当前配置的 LLM、Redis 与解析产物。测试夹具不能代替真实 H3S 或正式论文提交流程。

```bash
conda run -n sc-wiki python -m pytest -q "tests/01_decentralized_uploading/test_fulltext_theoretical_subtype.py" "backend/tests/test_upload_jobs.py" -k "not test_normalize_legacy_li2mgh16_properties_into_scientific_material_state"
cd "frontend"
npm run test:upload-ui -- --run "../tests/01_decentralized_uploading/evidence-workflow.test.tsx"
npm run build
```

**预期**：专项分类测试覆盖三类、空值、附件、长文、来源定位、人工改值和隔离转接；侧栏组件测试与构建通过。被排除的 Li2MgH16 测试在本功能实施前已有材料状态归并失败，应独立处理，不能算作本功能通过项。

隔离浏览器夹具需要一个已启动的本地 Vite 服务和本机现有的 Playwright/Chromium。先在 `frontend/` 执行 `npm run dev -- --host 127.0.0.1`，再从仓库根目录运行：

```bash
FRONTEND_URL="http://127.0.0.1:5173" PLAYWRIGHT_MODULE="<本机 Playwright 模块路径>" CHROMIUM_PATH="<本机 Chromium 可执行文件路径>" node "tests/01_decentralized_uploading/field-evidence-browser.mjs"
```

**预期**：上传者、管理员、超级管理员在 1440/390/320px 均能看到理论二级类型的“全文归纳”、具体理由及原文片段；不出现逐字记载的通用兜底文案。该脚本截获全部 API，不会写真实论文或调用模型。`PLAYWRIGHT_MODULE`、`CHROMIUM_PATH` 应替换为本机安装路径；未安装浏览器时不能把脚本记为通过。

当前 H3S 的人工复核从上传任务列表进入对应 `ready` 草稿，记录任务 ID、当前值、原 AI 值、模型与来源批次数，再打开本字段侧栏。**预期**：当前值为 `calculation`，理由综合研究目标和物相、金属化、Tc 结果，代表片段可定位且不只来自 Methods；刷新后值和理由保持。只有确需重新计算、已经核对任务 ID 和文件名并留存重跑前状态时，才运行 `scripts/reclassify-theoretical-subtype.py`，它会修改目标草稿。其 `--task-id` 与 `--expected-filename` 均为必填，不应把复跑测试误写成只读核查。

```bash
conda run -n sc-wiki python "scripts/reclassify-theoretical-subtype.py" --task-id "<已核对的上传任务 ID>" --expected-filename "2014 H3S-段德芳.pdf"
```

正式路径的剩余验收应在隔离数据库执行：上传一个理论论文夹具，完成来源核对并提交，重读正式 `papers.theoretical_subtype` 与 `ScientificEvidenceSource`，再按既有审核流程批准并重读来源。**预期**：当前值、`paper_synthesis`、综合理由、模型与版本、重绑定引句一致；其他字段核对保持。测试必须回滚或清理夹具，不能借当前 H3S 草稿自动提交。本轮没有准备可销毁的隔离 MySQL，未对当前业务库创建测试论文；该项由 [T009](tasks.md) 跟踪，尚未记录为通过。

## 需求与证据矩阵

| 目标 | 已有证据 | 尚待证据 |
|---|---|---|
| FR-001/002/005、SC-001/002 | 真实 H3S 模型、三类/空值和全部来源组测试 | 无本次已知缺口 |
| FR-003/004、SC-003 | 来源校验、前端组件、隔离 Chromium 及已登录 H3S 页面只读核验 | 正式来源端到端（T009） |
| FR-006、SC-004 | 目标草稿重跑、人工改值保护、单字段哈希测试、已登录页面刷新 | 无本次已知缺口 |
| FR-007、SC-003 | 函数级文件 ID/引句重绑定测试 | 隔离数据库提交、批准及正式来源重读（T009） |

## 已有验收结果及其边界

本次文档复核按上面的命令重新执行：Python 64 项通过、1 项既有无关失败排除；侧栏组件 33 项通过；前端构建、`git diff --check`、本目录相对链接和 15 条需求质量检查通过。此前更大范围的 112 项 Python、55 项前端与隔离浏览器结果保留在下面的历史记录；本次未重新调用真实模型或伪称正式提交已验收。

2026-10-11 18:41 CST 在用户当前登录的 Safari 本地 `localhost:5173/upload` 页面，对 `2014 H3S-段德芳.pdf` 的 `ready` 草稿进行只读核验。刷新后论文整体类型仍为理论文章，二级类型仍为 `Calculation`；打开字段侧栏显示全文归纳提示、综合理由和 3 条定位原文，位置为第 1、4、4 页，内容分别涉及全文研究目标、高压相预测和 Tc 结果。理由明确区分已有 USPEX/VASP/QE 应用与新算法/理论模型；未出现逐字记载的通用兜底。页面没有保存或提交草稿。此结果完成 T010，不代表 T009 的正式来源验收。

## 真实 H3S 与模型

- 本机目标为唯一处于 `ready` 的 `2014 H3S-段德芳.pdf` 草稿，含正文与补充材料。全文分类读取 1/1 个来源组、约 39 千字符；模型为当前配置的 `deepseek-v4-pro`。
- 定向重跑前草稿和原 AI 值均为 `calculation`，未检测到人工改值；重跑后仍为 `calculation`。模型解释它用既有 USPEX/VASP/QE 预测高压相、金属化和 Tc，未提出新算法或解析理论。引句包含结果、讨论等正文位置，不只取 Methods。
- 新核对为 `supported`，`source_kind=paper_synthesis`，保存了综合理由与定位引句。旧 Methods-only 核对留在历史，其他字段的来源身份未因本字段规则而整体升版。
- 额外真实模型样本：以新结构搜索算法及基准性能为主的短文归 `method`；以解析配对模型和标度律为主的短文归 `theory`。无法判断或模型超时的空值由隔离用例覆盖。

## 自动化与界面

- Python 专项覆盖三类、Methods-only、同块标题、超长两窗口全部阅读、失败留空、用户编辑保护及单字段来源版本。来源核对与 RAG 归因复用原接口，不新增正式论文列。
- 前端来源侧栏组件测试通过。隔离 Chromium 对上传、管理员、超级管理员 × 1440/390/320px 验证“全文归纳”提示、具体 AI 理由及不再出现“原文直接记载，无需额外推断”；管理员可修改论文级理论二级类型。浏览器 API 使用截获夹具，未直接登录当前 Safari 会话。
- 真实模型输出与当前草稿写入通过；正式已批准论文未批量重新分类。当前库没有本功能已提交的正式 H3S 论文，因此正式来源转接由代码路径与隔离测试验证，不表述为已在正式论文上验收。

## 复核结果与边界

- 截图对应草稿重跑后，当前值仍为 `calculation`；最新字段核对为 `supported/paper_synthesis`，AI 理由说明现有计算工具如何服务于具体材料预测。最终侧栏来源限定为 3 条已定位的代表片段，包含结果和讨论；旧 Methods-only 结果作为历史保留。
- Python 定向 112 项通过；旧 Li2MgH16 材料状态归并测试 1 项与本功能无关且在原基线失败，定向统计中排除。前端 3 文件 55 项通过，TypeScript/Vite 构建通过。
- 隔离 Chromium 在上传者、管理员、超级管理员 × 1440/390/320px 均通过；页面展示全文归纳提示与具体理由，保留人工记录及原文区顺序。当前 Codex 浏览器连接缺少认证令牌，未直接操作用户的 Safari 登录页；浏览器验收使用真实组件和截获 API，不写论文或调用模型。
- 源转接的隔离测试覆盖草稿文件 ID 到正式论文文件 ID 的重定位、分析内嵌引句与 `paper_synthesis` 归因。当前正式库没有已提交的 H3S 论文，未实际批准或批量修改历史论文；来源转接在真实正式论文上的联调边界保留在本记录。
