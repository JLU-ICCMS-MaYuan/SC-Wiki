# 实施与验收记录：浅度论文解析

日期：2026-11-12。Issue：[#241](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/241)。

## 已落地行为

- 新网页上传完成后选择浅度或深度；服务器原子固定模式和一次入队权。未传延后标记的历史客户端保持默认深度。
- 浅度固定 paper-only 流程，仅提取全部现有论文级字段；不执行深度适用性判断、论文级核对、科学字段、结构、物性、谱图、引用匹配或审核。
- 编辑复用既有字段差量存储与工作稿凭证。draft-state/draft 位于 evidence 路由，但仅做存储和并发，默认不读取字段核对结果；没有另造保存协议。无变化保存零请求。
- 浅度提交复用正式事务，写 published 直接收录状态、论文及原文件、文本、作者身份和家族候选；审核人、审核时间与 approved_revision 为空，历史仅 uploaded，不伪造 reviewed。
- 研究材料可完整解析为化学式时写论文级 chemical_systems 索引；不创建 superconductor、材料状态、结构或物性。无科学数据时不满足压强/Tc条件。
- 搜索页新增标题/DOI/期刊入口；论文视图对访客和普通用户公开浅度论文，元素/化学式、去重、计数和分页沿原语义。详情为论文信息只读展示；旧通用修改接口不能留下过期的浅度检索索引。深度审核和 RAG 批准门保持。

## 真实来源与正式 Worker 验证

机器证据见 [validation-evidence.json](validation-evidence.json)。使用不包含原有5个未提交文件的源码投影，单独启动本机临时 MySQL、Redis 和文件目录；没有连接业务数据库。

- 来源：CaH6 正文 PDF，SHA-256 为 5a8f5279732264dc218b9ab865778768e37623127b8bd64bbce6135da101c8da。
- 原文读取：复用与原 PDF 哈希匹配的既有 Document IR，重新绑定本次隔离上传文件；未改文字提取器，没有复用旧字段提取答案。
- 模型：服务端默认 deepseek-flash。通过正式 process_upload_task 入口重新提取论文级信息，记录1个 paper_info_extraction 完成回执；本次输入17649、输出814、共18463 token。没有科学提取或核对阶段。
- 结果：标题为 Superconductive sodalite-like clathrate calcium hydride at high pressures，年份2012，DOI 10.1073/pnas.1118168109；研究材料清单含 CaH6 等原文对象。
- 正式后处理：沿生产字段差量保存，重读保留修改；注入提交失败后恢复 ready，恢复正常提交及重复提交只产生1篇论文、1份原文件。审核信息为空，只有 uploaded 历史，材料状态、物性、结构、字段核对记录均为0。
- 查询：同一隔离 MySQL 中用正式 Go SearchResults 和 GetPaper 验证匿名按标题和 CaH6 化学式命中，并打开 published 论文详情。
- 迁移：实际执行 #241 状态约束降级/升级；ORM隔离夹具仅修正旧模型 JSON/TEXT 默认值的 MySQL 表达式语法，不把该夹具宣称为全量fresh迁移或业务部署。
- 清理：脚本只停止本次持有的 MySQL/Redis 子进程并移除临时数据；报告保留。源码投影和原工作区分别验过正式提交与搜索。

复跑命令：

```bash
python scripts/verify_shallow_parsing_isolated.py   --pdf "<正文PDF绝对路径>"   --document-ir "<与PDF哈希匹配的IR绝对路径>"   --evidence-dir "<尚不存在的本次证据目录>"
```

脚本会真实调用当前服务端模型；使用独立 MySQL/Redis，不是已有任务的提交指令。运行环境须具备项目 Python 依赖、同前缀 mysqld/redis-server 以及 .local/go/bin/go。

## 自动回归与可复查日志

| 范围 | 结果 | 依据 |
| --- | --- | --- |
| 字段契约 | 21论文字段、11材料字段、3软件组基线通过 | npm run test:field-contract --prefix frontend；标准契约及摘要未修改 |
| 四类科学表单宿主 | 254项通过 | npm run test:form-contract --prefix frontend；Node 22，VITEST_MAX_THREADS=2、VITEST_MIN_THREADS=1；没有增加超时或放宽断言 |
| 变异 | 8项渲染、4项漏红均检出 | npm run test:form-contract:mutation --prefix frontend |
| Python相关边界 | 44项通过 | test_shallow_parsing、test_parsing_workflows、test_paper_first、test_upload_contracts、test_workflow_binding；提交投影同样通过 |
| 上传/搜索交互 | 45项相关回归通过；浅度专项最终5项通过，含完整上传页和任务切换 | shallow-parsing、manual-upload-files、human-questions、upload-model-activity、file-consistency-submit、search-navigation、search-results、search-filters、search-page-defaults |
| Go | 新浅度搜索及隔离MySQL详情通过；排除下列独立基线旧失败后全包通过 | go test ./... -skip '^TestApplyPaperEvidenceArchivesManualReasonInReviewTransaction$' |
| 前端构建 | tsc及Vite生产构建通过；保留既有大分包提示 | npm run build --prefix frontend |

本机日志按 scwiki241 前缀归档，必要结果保存在本目录和 .local/issue241-shallow-worker-final/；真实来源与源码指纹另已归档至上述机器证据，不依赖临时日志才能读取主要结论。

## 先失败再修复的边界

新增解析、模式和无状态搜索测试在实施前失败。后续用真实共享编辑器复现了“从深度切到浅度时，旧深度草稿触发新任务核对摘要”的问题；在请求边界绑定已加载草稿的URL身份，浅度草稿完成载入前不创建核对目标。对应 shallow-parsing.test.tsx 任务切换测试保存红绿证据，不靠卸载同一任务编辑器或清除所有缓存修复。完整上传页另检出了模式选择与解析详情使用相同 React key 的问题；先用错误日志断言确认失败，再用不同前缀保留各自稳定身份，最终完整宿主通过且无重复 key。

论文搜索增加第二个输入框后，#65 旧测试按唯一textbox定位不再成立；为原 Formula 控件补齐标签关联，并按明确可访问名称定位，仍严格断言空值，未放宽原验收。

## 独立基线中已经存在的失败

从 ec299f10 的未修改源码归档建立独立副本，不切换工作分支，也不带原有五个未提交文件：

- Go TestApplyPaperEvidenceArchivesManualReasonInReviewTransaction：旧SQLMock仍期望删除 scientific_evidence_checks；未修改副本同样失败。全量首次运行明确为失败，上表的排除结果不冒充全量通过。
- backend/tests/test_upload_jobs.py 中旧结构候选绑定测试：仍期望按压强自动指定旧 structure_candidates；未修改副本同样失败。
- backend/tests/test_upload_workflow.py 的3项旧夹具失败：保存原子性夹具、旧材料派生提交夹具、缺 scientific_manual_evidence 表的提交失败夹具，在未修改副本均失败；该组当前34通过/3失败/3跳过，未修改副本33通过/4失败/3跳过，额外失败为其临时文件权限，未归为本次通过。
- paper-detail-route.test.tsx 的3项旧用例仍要求“我的论文”旧文案、旧列表请求和旧空态；未修改副本相同3项失败（13通过）。

没有修改这些独立旧失败的断言，也没有将其归为本次修复或通过。

## 验收覆盖与环境边界

SC-001对应真实提取、字段保存与正式重读；SC-002对应零科学/核对/审核路径及模式切换回归；SC-003—004对应匿名正式搜索、无状态匹配、科学条件排除、分页与去重；SC-005对应正式失败恢复/幂等及既有深度回归；SC-006对应原文、模型、源码投影及契约/变异证据。

这是本次受影响路径的隔离验收，不等于深度整篇科学解析重新验收、全站性能验收或远端CI通过。本机业务库和阿里云均未执行迁移、发布或数据回填；使用浅度直接收录前需要在明确目标环境应用 20261112_0241 约束迁移。未推送 origin-demo，远程 Spec 链接待验证，Issue 保持开放。
