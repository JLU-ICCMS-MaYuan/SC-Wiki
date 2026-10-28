# 文件身份一致性修复验收

日期：2026-10-28。[本轮规格](identity-consistency-fix.md)，[Issue #135](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/135)。

## 结论与范围

- 新提取入口不再把文本首行直接当标题，保守识别首页论文标题、自身 DOI；页码、页脚、SI 通用标题、编号章节和引用 DOI 不制造身份冲突。
- 正文与 SI 的比较使用最终有效角色及来源版本。缺失为 unknown；明确的不同标题/DOI 仍为 warning。产品检查和提交确认没有新增模型调用。
- 原生提交确认框展示实际冲突的文件名、字段及两边值，并携带当前冲突/文件版本令牌；取消不继续，来源变化拒绝旧确认。
- 指定本机 La–Sc–H 任务 `c16cc627a0c04dc8ad4289624d1da80a` 已由旧 warning 重算为 ok，冲突 0；草稿原字节和全部科学字段核对结果指纹未变化。实际 HTTP 读回仍有 1,111 项人工确认、0 项待核对。未代为提交论文。

## 原文件与真实提取

| 文件 | 原文件 SHA-256 | 已核验来源及结果 |
|---|---|---|
| 2024 La-Sc-H 何新玲.pdf | `7fccce6780e71f826519256542a5416f5b256e1aa2b546b68e194468688e2bbd` | 首页标题为 Predicted hot superconductivity in LaSc2H24 under pressure；DOI 为 10.1073/pnas.2401840121 |
| 2024 La-Sc-H 何新玲-SI.pdf | `a8db19670dfc30948c14d9792133288d8382588d84822f51666e5c36a476db3c` | 首页标题相同；没有自身 DOI，保持空白 |

先校验原文件哈希，再复用原有 Markdown；用 PyMuPDF 从原 PDF 首页核验标题/DOI。未修改文字提取模块，未重提整篇。正式身份提取入口重新执行，没有读取草稿标题作为答案。

在隔离验证中实际调用 `deepseek-v4-pro`：一次请求包含两份首页，只重新提取标题/DOI和逐字引句；不提供预填答案，不复用旧 AI 提取输出。第一轮通过后补强未标注参考文献干扰规则，重新执行一次验证；两轮原始输入/输出均保留，每轮 1 次调用，共 2 次。最终输出与正式规则一致，随后进入同一比较函数，使用正式 persist_upload 在真实 MySQL 隔离事务中保存、重读并回滚。该真实模型调用只用于验证，不是提交的新前置条件。

输入、输出、调用统计、模型身份、源码哈希、来源哈希及隔离回读结果保存在 `.data/135-file-identity-20261028/`；第一轮在 `first-validation/`。精简核验材料见 [结果](assets/2026-10-28-identity-verification.json)。本轮只证明身份字段及提交交互，不证明全篇提取或科学结论正确。

## 测试

- `test_document_identity.py` 与 `test_spectrum_submit_mysql.py`：13 项通过，覆盖旧首行错误重放、正式 Worker 委托入口、角色修正、标题排版/换行、真实化学式和 DOI 差异、缺失/噪声/引用、确认过期，以及真实论文提交事务仍能保存未采纳谱。
- `file-consistency-submit.test.tsx`：2 项通过，实际 UploadTaskEditor 提交、具体差异文本、取消与确认版本。
- `file-identity-browser.mjs`：正式 React 上传路由、真实 Chrome 原生确认框通过；2 次对话框（先取消、再确认）、3 次隔离提交请求，模型任务 0，页面错误 0。API 由隔离夹具拦截，不操作真实论文。
- TypeScript/Vite 构建通过，保留既有 3Dmol eval 与大分包警告。

较广旧套件 `test_issue24_task_contract.py`、`test_document_roles.py` 有 4 项失败：上传前必须恰好一个正文的旧断言，以及三项旧文件路径/缓存夹具与当前存储契约不符。将 Git `1287b567` 的 backend/scripts/tests 解出到临时目录，以相同环境独立运行后同样为 4 失败、13 通过；本次工作树相同四项失败，新增身份测试通过。基线日志保存在 `.data/135-file-identity-20261028/baseline-tests.log`，未把旧套件称为全通过，也未扩大本轮修改范围。

## 定向数据修正

工具为 `scripts/repair-upload-file-identity.py`，固定上述任务，默认只盘点。`--verify-model` 为隔离验证；`--apply` 要求当前来源与源码版本匹配的验证报告，目标锁内再查文件与任务状态，保存备份后仅更新 consistency 和新增修正审计；旧警告仍在审计中。

备份目录为 `.data/135-file-identity-20261028/`，`before.json` 的 SHA-256 是 `44f791e3c29baeab0e9c4f684cb13dcc5ec5d53d8141dbf7baaca390d08bc5f3`。科学字段核对记录未写入；草稿原字节不变；Redis/MySQL 重读一致。重复执行返回 already_repaired，状态和修正审计无新增。实际接口读回 consistency=ok、conflicts=0，原来的人工审核结果不失效。

首次应用在写入备份前遇到 Redis 返回字符串的哈希类型错误，未发生任务数据写入；修正编码后执行通过。没有清空科学字段、重算谱、全量修改其他任务、推送或发布到阿里云。

## 文档与关闭边界

本轮需求、Plan、Research、数据/接口、Tasks、图片清单与 Overview 已同步。根 README 的安装启动和操作入口不变。远程文档仍待授权推送后核验；保留 #135 其他验收和开放状态。共享 upload_jobs 中的并行修改只保留在工作区，本次仅提交身份入口差异。
