# 数据模型：多模态 PDF 解析与证据驱动上传 Agent

**GitHub Issue**：[ #114](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/114)

## 归属和版本

文档 IR 属于 `paper_file + paper_revision`；上传任务阶段暂存在 artifact，正式提交时在同一论文事务中持久化到新的当前 revision。解析器不拥有科学数据写入权。所有正式定位都带源文件 SHA-256、解析方案、解析器名称/版本、IR 版本和规则版本。旧 revision 不作为可长期打开的完整文档保存，现有修改历史仍按既有机制记录。

## DocumentSource

| 字段 | 约束 |
| --- | --- |
| `file_id` | 任务/论文 revision 内稳定身份 |
| `paper_file_id` | 正式论文可空，提交后关联 `paper_files.id` |
| `role` | `main`、`supplementary`、`attachment` |
| `sha256` | 64 位文件摘要，定位和缓存的前提 |
| `original_filename` | 原始名称快照 |
| `media_type` | 由服务端判断，不信任前端声明 |
| `source_version` | 同文件内容版本，内容变化即递增 |
| `parse_profile` | 任务选择的解析方案，如 `text`、`layout`、`ocr`、`vision`、`native_pdf_llm` |

媒体路由固定为：PDF 进入上述解析方案；TXT/MD 继续直接读取；CIF/POSCAR 继续进入 ASE 结构候选流程，不进入 PDF Parser。

## DocumentIR 与 DocumentBlock

`DocumentIR` 是一份文件按指定解析方案生成的不可变快照，包含 parser、mode、capabilities、pages、blocks、tables、figures、formulas 和 CoverageReport。解析方案不可用时不自动换用另一方案；该次运行进入失败、可重试或人工处理状态。

`DocumentBlock` 至少包含：

| 字段 | 约束 |
| --- | --- |
| `block_id` | 在 file/version/parser 范围内稳定 |
| `block_type` | `paragraph`、`heading`、`table`、`table_cell`、`figure`、`formula`、`caption`、`ocr_text` |
| `pdf_page` | 从 1 开始，必须存在 |
| `printed_page` | 可空，不能替代 PDF 页码 |
| `reading_order` | 同文件非负序号 |
| `text` | 解析或 OCR 文本，可为空于纯图像块 |
| `bbox` | 可空四元组，必须在页面边界内 |
| `polygon` | 可空且点数至少 4，必须在页面边界内 |
| `parent_block_id` | 可空，表格/单元格等层级关系 |
| `table_id` / `figure_id` | 可空稳定身份 |
| `confidence` | 0–1，可空但视觉块应尽量提供 |
| `content_hash` | 规范文本/几何/类型摘要 |

正式数据库建议新增 `paper_document_blocks`，以 `paper_id + paper_revision + paper_file_id + parser_run_id + block_id` 唯一；表格行列和 IR 元数据以 JSON 保存，但核心页码、类型、哈希和几何列独立保存以便查询。只有当前 revision 的正式运行进入该表，Shadow 运行保留在对照 artifact 或独立运行记录中。

## Claim 与 EvidenceLocator

Claim 是进入现有草稿转换前的中间事实，不等同于 `property_records`。字段包括：

- `claim_id`、`target_path`、`value`、`raw_value`。
- `basis_kind`：`paper_quote`、`paper_inference`、`general_knowledge`。
- `source_kind`：`text_layer`、`ocr`、`vision`、`derived`、`external_metadata`、`external_background`。
- `status`：`candidate`、`validated`、`uncertain`、`rejected`。
- `confidence`、`rule_version`、`content_hash`。
- `evidences[]`：file_id、source_version、pdf_page、printed_page、block_id、bbox/polygon、quote、parser/version。

只有 `paper_quote`、`text_layer/ocr/vision` 且通过定位校验的 Claim 才能自动成为论文科学字段候选；`paper_inference` 必须作为推断建议。`general_knowledge`、`external_metadata` 和 `external_background` 不能自动写入科学记录，但沿用现有人工采纳和管理员裁决路径时必须保留来源类别、理由和版本。

## CoverageReport

保存：已处理页、空页、表格及行数、图像/公式块数、疑似结果块、已覆盖 Claim、未覆盖候选、截断信号、所选方案限制、检查器版本和完成状态。`complete` 只有在所有检查器通过或明确记录人工接管时成立。

## ParserRun

保存一次解析的任务/文件身份、所选方案、解析器、版本、模式、能力快照、开始/结束时间、状态、error_code、error_summary、模型版本、IR 版本和规则版本。错误摘要不得包含堆栈、密钥或服务器路径；不保存 `fallback_from`，因为解析器不会在本次运行中静默切换。

正式运行元数据建议保存于 `paper_document_parser_runs`；Shadow 运行可以只保留在对照 artifact 或独立评测存储中。`paper_document_blocks.parser_run_id` 必须引用同一文件、同一当前 revision 的正式运行。

## 生命周期

主任务阶段仍为：`extracting → reading → summarizing → ready`。

`reading` 内部子状态为：

~~~text
parsing → ir_ready → claims_ready → coverage_checked
                    ├──────────────→ degraded → needs_review
                    └──────────────→ failed → retrying → parsing
~~~

`degraded` 只表示所选方案的结果存在明确限制或不完整，不表示系统自动选择了另一种方案；用户或任务策略需要显式选择其他方案后重试。

正式提交：在论文创建/升版事务中，将有效 `DocumentBlock` 写入新的当前 revision，并通过定位关联表连接现有 `PaperEvidence`；失败整体回滚。旧 revision 不保留为可长期打开的完整文档。论文删除沿用现有文件/片段/Evidence 的级联规则。旧缓存无 IR 时使用现有 `paper_chunks` 页码和 quote 读取，并明确标记为旧文本定位。

## 定位关联表

新增 `paper_evidence_locators`，用于把现有 `paper_evidences` 与区域级文档块连接起来。每行至少包含：

- `paper_evidence_id`、`paper_id`、`paper_revision`、`paper_file_id`、`parser_run_id`、`document_block_id`。
- `pdf_page`、可选 `printed_page`、可选 `bbox/polygon`、可选 `table_id/figure_id`、`quote`。
- `source_kind`、`parser`、`parser_version`、`source_version`、`locator_hash`。

表的复合外键必须保证 Evidence、PaperFile、DocumentBlock 和 Paper 属于同一当前 revision；删除、升版和事务回滚沿既有级联边界处理。旧 `paper_evidences` 没有区域时不创建伪造定位行，前端继续读取页码和 quote。

## 关系与不变量

1. DocumentBlock 不跨文件、跨 revision、跨 parser run 或跨内容哈希复用。
2. EvidenceLocator 的 `file_id`、`source_version` 和 `block_id` 必须能定位到同一 IR。
3. Claim 不直接持有数据库科学实体 ID；转换后由现有草稿稳定键生成。
4. 正式科学字段没有有效 Evidence 时不得自动写入；人工推断必须保留来源类别和理由。
5. 页面截图不是持久事实，截图失败不删除文本定位。


## 当前事务实现

`paper_document_parser_runs.document_json` 保存当前 IR 的页面、表格和区域快照，正式
保存时 file_id 转为 paper_files 的 ID。创建论文的原事务同时保存运行、块和定位关联，
任一步失败整体回滚。引句有歧义时保留旧文本证据，不生成虚假区域。

升版约束采用单一更新路径：File → ParserRun → DocumentBlock；Evidence → Locator。
Locator 另以不含重复 revision 列的不可变块身份外键连接 DocumentBlock。两条链都归属
同一论文当前 revision，避免 MySQL 多路径更新同一 revision 列；同一来源文件与引句
一致性由关联服务再次校验。截图不落盘。旧 revision 不新增全文归档。
