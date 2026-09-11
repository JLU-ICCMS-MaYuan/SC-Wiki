# 验证路径

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
