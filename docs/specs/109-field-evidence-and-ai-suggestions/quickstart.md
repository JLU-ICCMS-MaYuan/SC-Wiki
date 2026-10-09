# 验证与结果

2026-09-18 本地验收。全部存储写入使用测试夹具或外层回滚；浏览器接口全部截获。没有修改真实论文，没有部署、推送或重建正式索引。

## 需求到验证

| 范围 | 实际结果 | 边界 |
| --- | --- | --- |
| FR-001—003 全字段和侧栏 | Vitest 50 项通过；三入口各在 1440、390、320px 通过 | 浏览器使用真实组件和隔离 API |
| FR-004—007 生成、采用、复核 | Python 106 项通过；真实模型两次调用产出并复核三类建议 | 合成文本验收，不是准确率或性能评测 |
| FR-008—009 待审、批准、来源 | MySQL 4 项回滚测试；真实 Python 结果进入 Go 门禁及 MySQL 归档/回滚测试通过 | 外部向量索引发布未执行；归因转换函数已测 |
| 保存和失效 | 空温压、派生采用、同引句不同文件、跨批次候选、历史、并发理由及失败恢复均有回归 | 旧判断不能批准新值 |
| Go 与构建 | `go test ./handlers -count=1` 通过；TypeScript/Vite 构建通过 | 外部 MySQL 用例默认跳过，专项另行显式执行 |

## 自动化命令

Python 使用项目 conda 环境。以下命令的内存数据库与测试密钥只用于隔离测试：

```bash
JWT_SECRET_KEY=fixture-only DEBUG=false DATABASE_URL="sqlite:///:memory:" \
"/home/mayuan/miniconda3/envs/sc-wiki/bin/python" -m pytest -q \
"tests/01_decentralized_uploading/test_field_suggestions.py" \
"tests/01_decentralized_uploading/test_evidence_proposals.py" \
"tests/01_decentralized_uploading/test_scientific_evidence.py" \
"tests/01_decentralized_uploading/test_property_evidence.py" \
"tests/01_decentralized_uploading/test_evidence_draft_version.py" \
"backend/tests/test_upload_jobs.py" "backend/tests/test_property_record_conditions.py"
```

前端命令：

```bash
"frontend/node_modules/.bin/vitest" run --config "vitest.config.ts" \
"tests/01_decentralized_uploading/scientific-evidence-markers.test.tsx" \
"tests/01_decentralized_uploading/evidence-workflow.test.tsx" \
"tests/01_decentralized_uploading/evidence-drawer-close.test.tsx" \
"tests/01_decentralized_uploading/evidence-draft-queue.test.tsx" \
"tests/01_decentralized_uploading/evidence-proposals.test.tsx" \
"tests/01_decentralized_uploading/crystal-structure.test.tsx"
```

在 `frontend/` 执行 `npm run build`；在 `goserver/` 执行 `go test ./handlers -count=1`。存在既有 spglib/passlib 弃用警告和构建包体积提示，没有新增失败。

## 真实存储与跨语言验证

显式加载本地配置后，设置 `SCWIKI_CURRENT_MYSQL=1`，运行 `test_field_suggestions_mysql.py`，全部写入位于外层回滚事务：

1. 保存并重读无引句的通用知识候选，采用后准备和应用到上传值，允许进入待审。
2. 上传转论文后，没有管理员理由则拒绝；填写理由后保留 `general_knowledge`、最终内容摘要和人工身份。永久来源重读及 RAG 归因保留推测；清空当前可选值仍保留只读历史。
3. 后台使用旧任务快照完成复核，不能覆盖数据库中更新的人工理由。
4. 尚未提交的旧支持候选被新复核质疑后退出接受状态，值和理由输入保留。
5. 已保存候选但最终绑定失败，再对新值复核得到反对结论；恢复准备与直接重试最终绑定均拒绝沿用旧通过资格。

设置 `SCWIKI_EVIDENCE_CONTRACT=/tmp/scwiki-109-approved-contract.json` 可导出该测试产生的真实服务端准备形状。Go 专项 `TestCurrentMySQLFieldSuggestionsContract` 读取它，使用事务内新建的合成论文验证无人工理由拒绝、含理由接受、归档失败回滚、成功归档重读及空字段保留。其 MySQL DSN 由当前 `DATABASE_URL` 在进程环境中转换，不打印凭据，不运行数据库迁移。

## 浏览器验证

设置 `PLAYWRIGHT_MODULE`、`CHROMIUM_PATH` 和 `FRONTEND_URL` 后运行：

- `field-evidence-browser.mjs`：上传、管理员、超级管理员 × 1440/390/320px，空态、通过项、人工理由、批准状态重开、Enter/Space/Escape、关闭保持位置、编辑当前值、查看零模型调用及管理员一次全量复核。
- `evidence-drawer-browser.mjs`：两种管理员角色，遮罩、Escape、关闭、返回修改和完成后的滚动/焦点恢复；无顶部已接受列表。
- `scientific-layout-browser.mjs`：多材料、折叠、结构切换、三维与只读参数、上传保存/提交、管理员保存和窄屏布局。结构参数标签的精确来源与键盘行为另由 Vitest 覆盖。

三组均通过。截图在本地 `/tmp/scwiki-109-browser/` 和 `/tmp/scwiki-scientific-layout/`，日志在 `/tmp/scwiki-109-*.log`。这些是隔离页面验收，不是线上论文审核结果。

## 真实模型验收

使用已配置的服务端默认模型 `gpt-5.6-sol`，仅发送合成的常压锡测量文字；三个字段分别明确要求标题、依据观测作出的推断和通用知识机制候选。实际执行一次 `generate` 和一次 `review_all`，共 71.9 秒。

| 候选 | 返回依据 | 独立复核 |
| --- | --- | --- |
| 原文标题 | `paper_quote`，真实合成引句 | 合理，原文直接记载 |
| 由约 3.7 K 零电阻与抗磁响应判断超导 | `paper_inference`，保留引句及推断限制 | 合理，仍为推断，`supported=false` |
| 可能的电声耦合机制 | `general_knowledge`，说明本文未研究机制 | 合理，仍为推测，`supported=false` |

输出节选保存在 [模型验收记录](model-acceptance.json)。复现脚本为 `field-suggestions-real-model.py`，必须显式设置 `SCWIKI_REAL_MODEL=1`；结果文件可由 `SCWIKI_MODEL_RESULT` 指定。未新增联网搜索，也未把这些合成候选保存到真实论文。此验收证明调用、类型/引用校验及生成与复核路径可用，不证明任意论文的判断正确率。

## 2026-10-09 新增验收路径（待实施，以下不是通过记录）

1. 使用可复现的 H3S 正文与补充材料夹具生成上传草稿。打开“标题”等已支持字段，确认首屏直接显示来源文件、第 6 页和实际引句，PDF 区域可进一步打开；“没有替换建议”不遮挡来源。
2. 对有多个关键论断的概括字段核对相关引句，对没有可定位引句的“材料维度”及缺少已核验输入的派生字段核对状态：不得仅凭 AI 理由显示当前值受支持；重查后若取得可靠依据才可转为支持。
3. 模拟 PDF 区域图片加载失败、跨文件同名引句、字段修改及旧规则版本。已有引句仍可读，文件和页码不串项，旧结论只读且不授予当前通过资格。
4. 在上传、管理员、超级管理员三个入口分别用鼠标和键盘查看支持、问题、空值、推断和人工来源；查看零模型调用，保存/提交/批准后重开仍能核对当前来源。
5. 先运行 T011/T013 的定向回归，再验证真实数据库转接及实际浏览器首屏。只在相应结果可观察且 SC-006—008 均满足后记录为已通过，并回写 Overview、README 与 Issue。

### 人工修改与证据验收（US5，同样待实施）

1. 打开作者、Tc 与结构字段，确认侧栏不显示“当前内容”JSON；系统原文区位于首位且默认展开，可手动折叠。分别让文本引句和已定位 PDF 图像作为支持，验证文件与位置可读；图片不可用时不显示伪区域。
2. 人工修改一个字段，先只自动保存半成品，再明确提交：无理由时按字段阻止；上传文字/PNG/JPEG/WebP/TXT/MD 后仍缺理由时阻止；无任何证据时还必须填写缺证原因。改回原值后不触发新增修改门禁。
3. 刷新、切换材料状态、重复上传、重新提交与上传转论文后，检查证据、理由、真实提交者和当前版本一致；旧值的证据仅留历史。无权限账号访问预览接口为 403，任务取消不删除正式历史文件。
4. 审核 AI 分别处理文字、可读取图片与不支持图片的模型：只在真实读取后显示已读；人工截图始终标为人工来源，不能被引用为论文原文。管理员独立核验与批准门禁保持有效。
5. 运行 T017/T018 的失败用例、前后端定向回归和真实 MySQL 回滚及浏览器流程；通过后记录 SC-009—012 的逐项证据，再更新当前功能总览与使用说明。当前文档仅定义预期，不表示这些验证已通过。

## 2026-10-09 实施进度与验证边界

已写入共享侧栏、独立人工证据表及私有文件接口、上传/返修/批准门禁与转接、v7 来源资格规则和审核 AI 独立人工来源输入。侧栏首区默认展开，证据区与建议区分开；修改差异、作者列表及历史值以可读组件显示。人工截图只有成功传给可处理图片的模型时才记录为已读；模型拒绝图片时回退文字核对并记录未读。上传者与审核员的当前版本材料同时进入复核输入，旧 revision 的材料可作为只读历史预览。

| 验证 | 结果 | 尚未覆盖 |
| --- | --- | --- |
| #109 定向 Python、区域和提取质量用例 | 32 项通过；包括无理由、缺证原因、版本失效、文件类型/大小/数量、哈希、历史、转接前再次校验、审核图片批次容量及上传者与审核员材料隔离 | 完整上传/返修/批准的真实 MySQL 事务 |
| 前端证据相关 Vitest | 8 个文件、60 项通过；覆盖侧栏顺序、可读值、历史预览、只读已提交记录和可信 PDF 区域 | 实际浏览器的桌面/窄屏与键盘验收 |
| Go handlers 与前端构建 | Go 全量通过（临时 Alpine 内启用 CGO）；`npm run build` 通过 | 部署制品与目标服务联调 |
| MySQL 存储边界 | 本机 MySQL 会话级临时表的 JSON 保存、重读和事务回滚通过；连接关闭后临时表消失 | 本机业务库仍在 `20260914_0052`，未执行 `20261009_0126` 或完整迁移链 |
| 旧范围 Python 回归 | 109 项通过，2 项失败 | 两项失败分别为既有 Li2MgH16 旧归一化预期不符、旧 Worker 测试夹具缺少 `user_id`；与本次差量无交叉 |

真实桌面浏览器控制因 Mac 锁屏和 Codex 浏览器令牌不可用而失败。一次性 MySQL 8.4 镜像拉取被仓库网关返回 502，未启动或修改测试容器；真实多模态模型调用尚未执行。因此 SC-006—012 仍保持待验收，#109 保持打开。本次代码与文档可独立审查，但不能把本机页面当作人工证据功能已上线：未迁移时人工证据接口明确返回 503。

## 审查和文档（原范围历史验收）

独立只读审查发现并修复了跨批次候选丢失、派生采用被阻塞、空温压异常、旧人工理由覆盖、上传旧值显示、旧接受资格绕过新复核、失败恢复窗口及历史转接丢失。README、上传解析、审核操作和 RAG 来源说明已同步。本任务复用已有字段定位、结果存储和批准事务，没有新增表或第二套表单。

提交前将本任务暂存内容导出为独立副本，复验 Python、前端、Go 和构建，确认不依赖其他会话未提交的分类修复；README 与页面重叠文件按差量暂存，原有表单定义、迁移及其他任务修改未纳入提交。作者角色记录合并到作者字段入口，上传转接后值发生变化的项目只保留为历史，不授予当前批准资格。
