# PDF 解析管线

## 功能说明

本功能描述上传任务从文件接收到生成待校对草稿、再到提交落库与发布向量索引的完整处理链路，是 01 目录的主线文档。文件校验与摄入约束见 [PDF 摄入](pdf-ingestion.md)；晶体结构附件的审核与默认结构选择见 [上传、审核与默认结构](upload-review-and-default-selection.md)。

## 入口与任务创建

- 前端入口是 `/upload`。用户声明一组文件，每个文件带 `client_id`、`role`（`main` / `supplementary` / `attachment`）、文件名和大小；支持 PDF、TXT、MD、CIF、POSCAR，单文件最大 50 MB，同时上传最多 3 个。
- `POST /api/upload-tasks`（`backend/api/upload_tasks.py`）调用 `create_task`：任务状态存入 Redis（带 TTL），同一用户活动任务上限 100；`TASK_ID_PATTERN` 为 32 位十六进制。请求只保存文件声明，不保存界面语言或展示建议副本。
- 上传的原始文件落盘到 `upload_PDFs/{task_id}/`，状态中记录 `sha256`、大小和角色。
- “开始上传并解析”后，任务被推入 RQ 队列 `scwiki-upload`，由 worker 容器（`rq worker --with-scheduler scwiki-upload`）执行 `backend.ingest.upload_jobs.process_upload_task`（`backend/ingest/upload_jobs.py`）。
- 本地开发环境由 `watchfiles` 监视 `backend/` 下的 Python 源码；源码变化时完整重启上传 Worker 子进程，避免长期运行进程继续使用旧模块缓存。Docker Worker 仍随容器启动并使用既有并发配置。
- 上传 Worker 注册队列级异常回调：如果 RQ 在导入或调用业务入口前失败，且对应上传任务仍处于运行态，任务会以 `error_code=upload_worker_execution_failed` 进入可重试的 `failed`，保留失败前阶段并使用固定安全错误摘要；已经由业务流程写入的终态不会被覆盖。
- 入队时把当前请求的 LLM 配置写入独立的 `upload:llm:{task_id}` Redis 瞬态键；Worker 开始处理时加载该配置，解析成功、失败、取消或任务清理时删除该键。公开任务状态最多返回 `llm_provider`，不包含密钥或完整配置。
- `/api/upload-tasks` 在 Docker 部署中由 Go 未匹配路由转发到 Python FastAPI；前端按约 2 秒间隔轮询 `/api/upload-tasks/{task_id}` 与 `/parsing` 获取进度。

## 五阶段状态机

`process_upload_task` 把处理过程划分为五个阶段，`stage_index` 与前端“第 X/5 步”一一对应：

| 步骤 | status / stage | 行为 | 主要产物 |
| --- | --- | --- | --- |
| 1 | 保存原始文件 | 文件落盘并记录哈希 | `upload_PDFs/{task_id}/` |
| 2 | `extracting` | 提取论文正文 | `parsed_markdown/{task_id}/{file_id}.md`、合并稿 `parsed_markdown/{task_id}.md` |
| 3 | `reading` | AI 分段阅读 | `review_artifacts/{task_id}/` 分段结果与 manifest |
| 4 | `summarizing` | AI 汇总草稿 | 归一化草稿（Redis）、`result.json` 快照 |
| 5 | `ready` | 等待用户校对 | 终态清理排程 |

### 第 2 步：提取论文正文（extracting）

- PDF 经 `pdf_extractor.py` 转为带页标记（`<!-- page: N -->`）的 Markdown；TXT/MD 直接读取；已提取过的文件直接复用缓存的 `.md`。
- CIF/POSCAR 原生附件不走文本提取，而是经 ASE 校验（`structure_extractor.build_structure_candidate`）生成结构候选；校验失败的候选标记为 `blocked`，等待人工处理。
- 任务解析生成的结构候选以 `material_state_ref="unassigned:*"` 标记，需在校对页「未分配结构候选」区分配到具体材料状态并确认（`material_state_ref` 变为 `material_states[N]`、`confirmation=confirmed`）后才会在提交时写入 `structure_models`；未确认的候选只作为附件文件保存，不落库。（[Issue #77](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/77)）
- 非结构 PDF 的正文还会经 `extract_structure_candidates` 从文本中抽取结构候选。
- 多文件任务逐文件处理并更新 `extraction_status`，全部完成后用 `compare_file_identities` 做身份一致性检查（同一论文的 DOI/标题线索），结果写入状态 `consistency`。
- 正文为空时直接失败（`论文正文为空，无法生成可校对草稿`）。

### 第 3 步：AI 分段阅读（reading）

- `chunker.py` 把合并前的各文件 Markdown 切成 `Chunk`，`_chunks_with_preamble` 为每个文件补一个前言段；分段清单写入 `review_artifacts/{task_id}/chunk_manifest.json`，每段状态在 `waiting / processing / completed / failed` 间流转。
- 读取前由 `_merge_extraction_windows` 把相邻小段合并为约 12000 字符的提取窗口（`EXTRACTION_WINDOW_CHARS`），页码取窗口起点所在页，再逐窗口调用 `_read_chunk`（使用当前请求选择的 OpenAI 兼容 LLM），减少过细分段造成的上下文断裂与调用次数。分段中的 AI 生成研究材料、方法和核心发现必须为英文；服务端在写入 `review_artifacts/{task_id}/chunks/` 前拒绝这些字段中的中日韩字符。论文标题、摘要和 `quote` 属于来源文本，保持输入语言，不翻译也不拦截；`quote` 可能来自 PDF 文本提取或 OCR，不承诺与扫描版逐字一致。
- 分段结果以 JSON 存到 `review_artifacts/{task_id}/chunks/`；任一分段异常（包括生成字段语言不符合约束）即整任务失败。
- 每完成一段更新 `completed_chunks / total_chunks`，前端进度条（如“4/28 段”）即来源于此。分段缓存契约版本为 9（`CHUNK_RESULT_SCHEMA_VERSION`），旧缓存重读时重新提取。

### 第 4 步：AI 汇总草稿（summarizing）

- `_summary_classification_candidates` 先过滤掉非当前论文的过期证据，再把分段候选交给 `complete_json(SUMMARY_SYSTEM_PROMPT, ...)` 汇总为一份结构化草稿。
- 汇总 prompt（`SUMMARY_SYSTEM_PROMPT`）与正文提取（`extractor.py`）都要求以英文产出六个叙述字段（`summary`、`keywords_tags`、`methodology`、`key_finding`、`research_motivation`、`knowledge_graph_title`）；汇总归一化后、写入草稿和审核快照前会再次拒绝这些生成字段中的中日韩字符。标题、摘要、作者、原始数值、单位和 `quote` 保持来源语言。Worker 以验证后的英文 canonical draft 预填选项框和输入框；字段建议在提取后单独生成，通过字段名打开侧栏查看；只有非空且能定位的 `quote` 才作为论文片段显示。某字段无来源依据时保持为空，不编造内容。（[Issue #74](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/74)、[#85](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/85)）
- 正文 PDF 在 Worker 中额外提交给本地 GROBID 的 `processFulltextDocument` 接口。GROBID 返回的 TEI `biblStruct` 会提取 DOI、题名、作者、年份和原始引文，随论文版本保存到 `paper_references`；GROBID 不可用或解析不完整时保存状态，不由 LLM 猜造引用边。（[Issue #81](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/81)）
- `_normalize_draft` 把草稿归一化为当前数据契约：论文元信息（含单选 `superconductor_kind` 和多选 Material family）、`material_states`（材料、压强/温度/磁场、计算与实验上下文、`tc_results`、More type labels）、分类证据等。旧草稿的状态级 `superconductor_kind` 只在读取时一次性提升：唯一的非 `unknown` 值保留，冲突时回退 `unknown`；新提交拒绝该旧字段。
- 化学式解析（`parse_formula_composition`）支持括号分组与 Unicode 下标，拒绝不配对或空括号；材料字段只在能唯一确定完整化学式时写入化学式（如 `(H2S)2H2` 不再截成 `H2S`），否则原文保留为材料名，替代式的元素数按组分统计；与空间群符号查表一致的空间群编号、晶系作为派生核对项随符号核对。（[Issue #120](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/120)）
- 汇总后执行查重：先按归一化 DOI（`normalize_doi`）查 `papers`，再按原始文件 SHA-256 查；命中即进入 `_handle_duplicate`，任务以 `duplicate` 状态短路结束。
- 草稿写入 Redis（`save_draft`），同时把 `ai_values` 与证据快照（分类证据、材料状态各字段证据）写入 `review_artifacts/{task_id}/result.json`。

### 第 5 步：等待用户校对（ready）

- `processing_status=succeeded`，任务进入可校对状态；`_schedule_terminal_cleanup` 通过 RQ scheduler 排程终态清理。
- 取消（`cancelled`）与失败同样进入终态清理排程；业务解析异常使用 `error_code=paper_processing_failed`，RQ 入口边界异常使用 `error_code=upload_worker_execution_failed`，两者都记录 `failed_stage` 并可在文件仍有效时重新解析。清理由 `cleanup_upload_task` 执行。

## 用户校对与提交落库

- 用户校对后先保存草稿，再执行共享的物性证据预检查；正式提交调用 `POST /api/rag/upload-tasks/{task_id}/submit`（`backend/api/rag.py`）。保存与提交共用任务锁，重复提交按已提交结果幂等返回。创建、文件上传和任务状态查询仍使用 `/api/upload-tasks`。
- `_create_pending_paper` 在一个数据库事务内完成：
  - 创建 `Paper`（`review_status=pending`、`content_revision=1`、`upload_task_id` 关联任务、论文级 `superconductor_kind`）与 `PaperFile`（角色、存储路径、SHA-256、排序）。
  - `persist_scientific_draft`（`backend/ingest/scientific_drafts.py`）把草稿落成科学实体图：`superconductors` → `material_states` → `structure_models`（含经用户确认的原生 CIF/POSCAR 附件，服务端重新 ASE 校验并以常规晶胞 CIF 为规范表示，不信任浏览器提交的校验/哈希字段）及 `property_modules` → `property_records`，并返回证据链接目标。计算和实验条件保存在各记录的 `payload_json`。
  - 预检查和正式提交共用 `source_chunks` 分段及页码传播；按文件、片段、页码和原文引句联合定位，写入 `paper_chunks`、`paper_evidences` 并挂接 `add_scientific_evidence_link`。同页多个片段通过引句区分，过时片段编号可由同文件唯一引句重新定位；不能唯一定位时返回记录路径与具体原因。
  - 经核对的多条证据及模型结论由后台保存到 `scientific_evidence_checks`；提交事务按稳定身份转接到正式论文，统一十进制摘要避免精度表示导致重复核对。
  - 违反完整性约束时整体回滚，返回 409 `scientific_data_integrity_error`。
- `_record_submitted_upload` 把 `ai_values / user_values / evidence` 快照写回 `result.json`，`cleanup_transient_data` 清理临时数据但保留审核快照；任务状态置为 `submitted`。

## 提交前补证与核对

上传与管理员独立 AI 审核共用 `/api/rag/evidence` 的预检查、任务创建、查询和取消接口。没有可复用结果时，
前端显示可取消的 3 秒倒计时，结束后才用发起用户当前模型配置创建 RQ 任务。模型只阅读当前论文及附件，
核对论文科学叙述及分类、材料状态、结构、物性、单位和条件；不会修改用户科学数据。引句必须能在来源文本中复核。

- 原文支持结论：核对完成后由用户点击提交，不自动续提。
- 有有效出处但存在冲突或歧义：允许用户提交为待审核，核对结论随正式记录保存，供管理员逐条裁决。
- 没有有效出处且没有采用可用建议：保留草稿，显示具体材料、物性、数值和原因，可让系统重新查找或返回修改记录。上传者明确采用标记为论文推断或通用知识推测的建议后，可以提交待审；管理员批准推测必须逐项说明依据。来源搜索、选择和关联由系统完成，不要求用户选择片段或编辑原文引句。
- 模型配置、超时、服务或队列失败：单独提示服务原因，原操作不继续，不归为表单填写错误。

上传解析自动生成字段建议；草稿 ready 后复用已有核对结果，仅对未完成项后台排队，校对页轮询同一任务。服务失败时页面有限重试一次，并显示错误和重新核对入口，草稿仍可编辑。管理员按钮重新复核全部字段、既有判断和候选，已有通过缓存不跳过。提交只检查结果、不调用模型；取消或离页均不自动提交，后台已完成结果继续保存。全量结果（包括未找到和未采用建议）在 MySQL 按科学内容、来源和规则版本保存，不依赖 Redis 任务有效期。重试只处理指定问题及派生依赖，已完成的其他项目不重复调用模型。历史论文不扫描或批量改写。

字段与来源核对按"记录组 × 来源批次"组合调用：来源剔除参考文献列表后整篇优先，超过约 120000
字符才分批，每批最多 20 条记录（`SOURCE_BATCH_CHARS`、`RECORD_BATCH`）。概括/推测与分类枚举字段
（`SYNTHESIS_FIELDS`，如 summary、research_motivation、keywords_tags、state_kind、crystal_system 等）
标记 `check_mode=synthesis`，仍由模型判断相关性，但 `supported` 至少需要一条可定位的当前论文依据；
只有 AI 判断理由而没有引句时标为缺证。聚合时忽略“本批未提及”；事实与数值字段仍执行逐字定位，
模型引句全部定位失败时回退使用提取阶段已通过逐字校验的记录自带证据再定位一次。
核对规则版本为 `scientific-evidence-v7`，旧结果按版本过期重核。
（[Issue #120](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/120)）
管理员的人工裁决及审核历史见[论文与记录审核](../02_Decentralized_Maintenance_and_Verification/literature-and-record-review.md)。
（[Issue #103](../../specs/103-property-evidence-review/spec.md)）

所有数据字段名均可点击，包括书目、空字段及只读结构参数。只有未解决的科学问题标红，每个控件的现有中英文说明文字聚合相关记录，不显示红点；无浮动标签时使用区域标题或文字入口。折叠状态显示去重问题数量；点击或键盘激活说明文字打开右侧覆盖抽屉，关闭后焦点返回。抽屉依次展示默认展开的“系统找到的原文”、人工修改记录和“AI 理由”，不设“当前内容”区，也不重复主表单的编辑控件或原始 JSON。文本依据直接显示真实文件与位置、引句；可信 PDF 图像区域打开字段时加载，失败时保留文字和位置。没有可定位论文依据时明确提示。有效的论文推断与通用知识推测在解析完成时补入主表单空值，侧栏只说明依据、推断与局限；历史明确接受草稿仍按原版本机制处理。通用知识推测可无论文引句，但不得伪造来源，正式批准仍需管理员依据。结构附件显示真实提交者、原始文件及解析依据，不要求手动选择片段或编辑引句。

人工修改的理由与证据独立于论文原文保存。直接文字、PNG/JPEG/WebP 截图及 UTF-8 TXT/MD 文件均须注明人工来源；单文件最大 10 MiB、单字段最多 5 项、直接文字最多 2 万字。草稿可暂存不完整说明，明确提交时每个实际修改字段均须填写简短理由，没有证据时还须说明缺证原因；改回原值不要求新说明。人工说明可使缺少论文出处的修改进入待审，不会把它改称原文支持。文件通过鉴权接口预览，不进入论文原文检索语料；部署需先执行 `20261009_0126` 迁移。

后台保存已定位证据并自动回写上传草稿；未找到证据的判断也持久保存。已核对草稿及必要原文不按普通 TTL 清理，刷新、离页和缓存丢失后均可恢复。正式提交仍按版本和权限重新校验。

等待后台核对时持续显示进度条与已等待时间。排队和未知总量显示动态等待条，开始分组后按实际完成组数
显示“已核对 X/Y 组原文”和百分比，并提示当前正在核对哪一组。计时不会推动完成百分比，取消与超时流程保持有效。

## 审核通过与向量发布

- 提交后的论文进入待审核队列，审核决策属于 02 目录的论文与记录审核。
- 审核通过后，管理员调用 `POST /api/papers/{paper_id}/publish`：`embed_and_index_chunks`（`backend/ingest/embedder.py`）把 `paper_chunks` 内容向量化并写入 Qdrant `paper_chunks` collection，此后 RAG 检索可用；论文未通过审核时调用返回 409 `paper_not_approved`。

## 实验条件提取

分段和全文汇总共用实验条件提示：以样品、制备方式、测量方法、测量装置、外场和压力不确定度
六方面引导 AI 输出英文自由描述，只使用原文事实，不要求六项齐全，不把缺失条件补成猜测。
每条测量 Tc 的条件分别写入该条 `experimental_conditions.description`，经既有草稿转换进入
`property_modules[].records[].payload.experimental_conditions.description`。同材料状态下的多条
测量结果不共享或相互覆盖条件；预测 Tc 保持计算 Conditions。分段缓存契约版本为 9，旧缓存
重读时重新提取。对应表单采用单个多行框；定义版本继续保存在数据内。（[Issue #94](../../specs/94-property-record-editor/spec.md)）

此链路通过模拟 LLM 返回、执行真实分段与汇总调用、草稿归一化、记录校验、SQLite 持久化及导出
验证；外部模型针对具体论文的输出质量仍需据原文审核。

## 当前边界与待核验

- 旧 Neo4j 作者及其他论文关系同步（`backend/ingest/sync_neo4j.py`）仍不在上传链路中自动触发；材料 `STUDIES` 同步已由 [#127](../../specs/127-retire-material-relations/spec.md) 移除。Issue #81 的论文引用图不依赖旧同步，公开查询直接读取 MySQL 中的 `paper_references`。
- `backend/ingest/PIPELINE.md` 描述的 `enrich_papers.py` → `clean_results/*.json` → `key_properties` 链路属于旧 `pipeline.py` 摄入路径；当前多文件上传链路不经过 `enrich_single` 与 `key_properties`。
- 解析质量依赖服务端默认 LLM 配置（`LLM_*` / `DEEPSEEK_*`）或用户请求中的临时配置；向量化发布仍独立依赖 Embedding 配置（`EMBEDDING_*`）与 Qdrant，用户供应商切换不改变 Embedding。

## 代码与测试

- 任务 API：`backend/api/upload_tasks.py`；提交与发布：`backend/api/rag.py`。
- 解析主流程：`backend/ingest/upload_jobs.py`；任务状态与存储：`backend/ingest/upload_tasks.py`、`upload_contracts.py`。
- 提取与分段：`pdf_extractor.py`、`chunker.py`、`extractor.py`；结构候选：`structure_extractor.py`；落库：`scientific_drafts.py`；向量化：`embedder.py`。
- 测试：`backend/tests/test_upload_workflow.py`、`tests/01_decentralized_uploading/`；其中 `test_issue91_upload_worker_recovery.py` 使用隔离 Redis 和真实 RQ Worker 覆盖入口导入失败边界。
- 共享核对：`backend/ingest/property_evidence.py`、`backend/api/evidence.py`、`frontend/src/components/EvidenceWorkflow.tsx`。现有 sc-wiki MySQL、真实模型及页面验收记录见 [#103 验证路径](../../specs/103-property-evidence-review/quickstart.md)。

共享抽屉区分未核对和 AI 未找到来源；理由/候选连续输入合并保存，失败暂停自动重试并保留输入。管理员能按当前版本逐条说明推理或专业判断依据，完成后作为人工来源放行；上传者可以采用已标注依据类型的建议进入待审，无管理员裁决权限。未核对草稿不会让后台漏查。

字段来源按 `paper_quote`、`paper_inference`、`general_knowledge` 区分直接记载、论文推断与通用知识推测；后两类经校验后自动补空值，保存与当前内容版本绑定的 AI 理由，不覆盖非空提取值。侧栏不重复表单值，顶部不再逐项铺开已接受记录。内容或来源变化后历史只读可查，批准后仍保留来源类别和人工理由。详见 [#109 设计与验收](../../specs/109-field-evidence-and-ai-suggestions/quickstart.md)。

## 可选结构化解析与区域证据（#114 部分实现）

上传页和创建任务 API 可指定 `parser_profile`。默认仍为 `legacy`；`layout` 使用
Docling 2.130.0 CPU 文本层/表格路径，`ocr` 使用 MinerU 4.0.6 basic OCR，`text`
使用 PyMuPDF。TXT/MD 与 ASE 结构附件保留原路由。`vision` 尚未注册；原生 PDF 的 OpenAI Responses 适配仅在部署允许名单和当前模型凭据
同时配置时启用，本机尚未完成真实服务验收，不在页面默认选项中开放。

重型解析在独立子进程运行，默认 300 秒超时后终止进程组；失败保留解析错误码，不换
其他方案。成功结果保存任务 IR，再产生带页码的文本供分段读取。新方案不复用旧
Markdown；分段缓存检查方案和文本摘要。区域统一为左上原点 PDF 点坐标，缺少表格
单元格坐标时只保存行列、跨度和限制。
本机 macOS 的上传 RQ Worker 使用 `SpawnWorker`，避免 fork 后加载 PDF/ML 原生库引发异常退出；
workhorse 意外结束时上传与来源核对任务都收敛到失败态，不继续显示运行中。

新 PDF 任务按连续页读取完整 IR 块与表格单元，使用版本 1 领域契约直接生成
`property_modules[].records[]`，不经过旧 tc_results 中转。未知方法保持 unknown，
每条结果保留独立条件与多页证据。全文汇总只生成书目与叙述，后端对科学候选精确
去重和组装，不由汇总模型重写数值或合并不同条件。TXT/MD 保留原提取与有界转换。
关键词由 AI 根据本文标题、摘要与研究内容提炼，原文没有关键词列表也可预填；编辑页提醒用户核对。若全文汇总遗漏且本文书目与叙述足够，再进行一次有界 AI 提炼；模型失败或内容不足时留空提示，不用规则拼接值冒充 AI 推理。Tc 以外的自动物性仅接受 `band_gap`、`dos_fermi` 两项，并归入电子性质专用定义；未注册的非 Tc 项带原文位置与理由留在覆盖审计，不自动进入自定义性质。该定义需要应用 `20261009_0115` 迁移，既有用户自定义记录不受此限制。
上传校对页重新获得焦点时会重读同一任务草稿及来源状态，让后台或协作补入的关键词出现在已打开的页面；存在未保存编辑、保存中或提交中时不覆盖本地输入。刷新失败保留当前草稿，下一次获得焦点可重试。
旧文本解析方案产生的未注册普通物性同样只留在 `unclassified_properties.json` 审计产物；不会改写此前已保存的用户自定义记录。结构表按物相拆分，已验证的空间群允许补足其晶系强制约束的晶胞参数，并在候选推导信息中标注；空间群和压力唯一匹配时才自动绑定材料状态。
领域候选转为 Claim 后，校验文件、页码、解析器版本、来源类别、块、区域
和原文；未知或有歧义的定位不自动通过。覆盖检查独立记录未覆盖页、结果段落、表格行
及图像/公式。有限补证只给同值候选补已验证出处，最多 12 次工具行动，每工具最多
2 次重试。仍有问题时保存检查产物并使用既有 failed 终态，不伪造 ready。
`ir_ready`、`claims_ready`、`coverage_checked`、`needs_review` 只作为 reading 子状态，
原五阶段不变。原文定位通过不代表科学语义正确，提交与批准继续经过现有核对和人工边界。

2026-10-08 实测（2014 H3S 主文 + 补充材料，Docling 2.130.0 CPU）验证了上述边界：
两个文件均成功产出 IR（合计约 3 分钟，含首次模型权重加载）；领域提取提示词原先未
给出 `method_code` 合法枚举，模型输出自由文本方法名导致契约校验稳定失败，现已把
predicted/measured 方法枚举写入提示词，服务端再把常见同义写法映射到枚举、无法识别
回退 `unknown` 并在 `method_raw` 保留原文，不再因方法名丢弃整篇解析。

覆盖检查自 2026-10-09（#122）起支持显式排除：领域提取契约新增 `coverage_exclusions`
（块/表行/页定位 + 受控类别：非结果内容、背景引用、无数据图、表头/单位行、模型范围外、
无法读取 + 理由），提取后对仍未覆盖项执行一次定向分类调用（每文件一次），明确非结果的
项转为带理由排除，确实需要提取的超导数据保持未覆盖并按文件计数写入失败信息。被排除项
不再计入未覆盖；`unreadable` 类别、以及疑似结果段落被大面积申报为"非结果内容"（超过
50% 且疑似块不少于 4 个）时保留人工复核。文本层为空的图/公式块是当前方案不读图像的
能力边界，只记录计数不要求覆盖。排除不是证据，全部处置（类别、理由、定位）记入
coverage.json 供审计。2014 H3S 实测：补充材料覆盖检查 complete（45 行晶格/坐标表
诚实标注模型范围外），主文仅剩 1 项需提取的谱函数段落明确列出，不再无差别整任务失败。
科学内容超出当前模块（能带隙、晶格参数、谱函数）时按 `out_of_model_scope` 记录，
后续注册相应模块后自然转为候选。

正式提交在原论文事务内保存 IR、文档块和 `paper_evidence_locators`，定位重新绑定
当前论文文件。升版沿现有当前代级联规则更新，不提供旧 revision 全文档案。
证据抽屉可按需请求 `/api/rag/evidence/region`，服务端校验目标归属和源文件哈希，
返回从原 PDF 直接渲染的 300 DPI 局部 PNG 与高亮区域；文字只截取引用句及同栏上下三行，
图表显示可信区域和邻近说明，不显示整页。图片按原始像素尺寸滚动，点击可弹出更大视窗，再点击缩回；
截图不保存。旧 `legacy` 来源虽未保存 IR 区域坐标，但可在点击时校验原 PDF 哈希，
文本层唯一匹配后补出实际页码；旧解析页码与 PDF 不符时以原 PDF 为准。没有文本层、
引句重复、文件变化或渲染失败时明确说明原因，原有引句仍可查看，不猜测位置。
当前待审标题优先核对正文主 PDF 首页，作者优先核对首页署名；已批准论文不批量改写。
历史审核条目不因此获得旧版本 PDF 浏览能力。

默认切换须由维护者提供当前已逐篇人工核对论文的详细比较报告，不再要求固定篇数或
一次覆盖全部类别；当前默认仍为 legacy。原生 PDF LLM 供应商、真实模型领域质量和浏览器整体验收仍未完成。隔离环境
已通过 HTTP/JWT、Redis/RQ、MySQL、Go 审核与返修端到端；模型响应固定注入，向量
发布使用测试替身。本机已执行 #114 三张定位表的增量迁移，不代表其他部署实例已
升级。验证范围见 [#114 验证记录](../../specs/114-multimodal-pdf-upload-agent/validation.md)。

维护者可用 `python -m backend.ingest.pdf_benchmark` 对逐篇积累的标注与成对运行结果做离线
比较，生成逐论文/逐类别的记录 F1、条件关联、区域定位、漏记录和资源报告。失败或
缺失论文保留分母，重复预测不能加分；缺少实测资源时保留空值。默认门要求版本 1
逐论文明细报告，核对当前已出现的类别不退步；未出现类别保留未验证状态。合成集及只有汇总数字的早期报告不能开启默认门。此工具不启动完整上传任务，
也不证明人工标注或独立事务验收的真实性；当前仍无真实基准报告。

配套 `pdf_benchmark_runner` 可调用本机 API 批量上传固定文件清单、轮询实际 Worker、
按原文件哈希导出 AI 初始结果与 IR 区域，并逐篇落盘。不会提交或批准论文，缺少
Token/GPU/费用实测数据时保持为空；CPU 只记录 Worker 进程自身时间。

`UPLOAD_PARSER_STAGE=shadow` 已接入独立对照作业；先复制并校验同一上传文件，
再使用配置的新方案生成内部产物。用户旧草稿、凭据、缓存及任务列表与对照隔离，
对照任务不能通过公开 API 补证或提交，不写科学数据库。结果比较只使用两份 AI 初始
产物，保存差异与失败原因；新方案失败不改变父任务，父任务取消后对照停止。
多个 Worker 可并行执行，单 Worker 顺序执行。完整灰度重新选择/回退验收仍待完成。

返修或管理员编辑采用新引句时，共享持久层在当前 IR 重建区域关联。后续迁移
`20260924_0114` 补齐 Tc 方法定义，本机已新增 9 个缺失定义，核对原定义校验和未变；
没有改写科学记录。回退应用保留已发布定义，避免破坏记录引用。
