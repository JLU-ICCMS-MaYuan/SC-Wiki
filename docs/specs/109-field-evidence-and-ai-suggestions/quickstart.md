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

## 审查和文档

独立只读审查发现并修复了跨批次候选丢失、派生采用被阻塞、空温压异常、旧人工理由覆盖、上传旧值显示、旧接受资格绕过新复核、失败恢复窗口及历史转接丢失。README、上传解析、审核操作和 RAG 来源说明已同步。本任务复用已有字段定位、结果存储和批准事务，没有新增表或第二套表单。

提交前将本任务暂存内容导出为独立副本，复验 Python、前端、Go 和构建，确认不依赖其他会话未提交的分类修复；README 与页面重叠文件按差量暂存，原有表单定义、迁移及其他任务修改未纳入提交。作者角色记录合并到作者字段入口，上传转接后值发生变化的项目只保留为历史，不授予当前批准资格。
