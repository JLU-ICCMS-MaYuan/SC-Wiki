# 四工具与知识库/数据库的开源组织方式调研

日期：2026-10-13。配套 [架构提案](four-tool-architecture.md)。结论来自公开文档与指定源码，不代表这些项目已在本机部署验收。

## 调研结论

没有找到足够证据证明“GROBID + MinerU + Docling + Marker 四者联合”是成熟主流标准方案。可核实的实践主要是：一个主解析器接统一内容接口；多种解析器作为可选后端；题录/引用专门链路；少数项目按内容类型组合多个引擎。不能把“支持多个解析器”写成“同一份文档会把多个结果互补融合”。

对 SC-Wiki 最有用的组合是：借鉴 RAG-Anything 的 MinerU 主干与按模态处理，借鉴 GROBID 文献库工具的题录/引用身份与原始制品管理，再为 Docling、Marker 编写范围明确的补强适配。知识库检索索引与已审核科学数据库分别处理，不把抽取概念图直接当论文引用事实。

## 检索范围与限制

通过 GitHub API 阅读官方/项目 README、树结构与实际源码；搜索 `grobid mineru`、`grobid docling`、`grobid marker`、`mineru docling marker`。仓库元数据检索前三组没有结果，不代表代码中不存在组合；代码检索 `grobid docling` 找到 VERA 的比较脚本，`grobid mineru` 本轮未得到结果。另对 RAG-Anything、RAGFlow、GROBID 的文献库生态做定向源码检查。这是有界调查，不是开源生态的普及率统计。

## 1. RAG-Anything：MinerU 主解析器，后接多模态处理与 LightRAG

提交：`da6e2d87a7d3f2746c4541f59953b8764213f6a2`。

- [`config.py`](https://github.com/HKUDS/RAG-Anything/blob/da6e2d87a7d3f2746c4541f59953b8764213f6a2/raganything/config.py) 第 29 行默认 parser 为 mineru，说明可选 mineru/docling/paddleocr。
- [`raganything.py`](https://github.com/HKUDS/RAG-Anything/blob/da6e2d87a7d3f2746c4541f59953b8764213f6a2/raganything/raganything.py) 通过 `get_parser(self.config.parser)` 建立一个文档解析器。
- [`parser.py`](https://github.com/HKUDS/RAG-Anything/blob/da6e2d87a7d3f2746c4541f59953b8764213f6a2/raganything/parser.py) 的 get_parser 按名字返回 MineruParser、DoclingParser 或其他注册器；不是默认同时跑多个解析器并融合。
- [`modalprocessors.py`](https://github.com/HKUDS/RAG-Anything/blob/da6e2d87a7d3f2746c4541f59953b8764213f6a2/raganything/modalprocessors.py) 区分 ImageModalProcessor、TableModalProcessor、EquationModalProcessor，结合上下文做后续语义处理。
- [README](https://github.com/HKUDS/RAG-Anything/blob/da6e2d87a7d3f2746c4541f59953b8764213f6a2/README.md) 展示解析后插入内容清单、文本与多模态处理、LightRAG 图索引与检索；允许插入外部已经解析的内容清单。

**适用借鉴**：MinerU 作为默认主干；保留表格/图片/公式的不同处理职责；用统一内容接口接知识库。**不能直接宣称**：它已有 GROBID+Marker 四工具互补，或其知识图自动满足 SC-Wiki 科学字段/论文引用规则。适配器仍包含 MinerU 2/3.x 风格 backend 参数；是否兼容本项目 4.0.6 的 tier 接口需要单独核实。

## 2. RAGFlow：可配置解析服务，接知识库分块和检索

提交：`fe8dc679abee02f0ac1be7cba7f53bb64dc2fb2f`。

- [`pdf_parser_common.go`](https://github.com/infiniflow/ragflow/blob/fe8dc679abee02f0ac1be7cba7f53bb64dc2fb2f/internal/parser/parser/pdf_parser_common.go) 第 372–377 行分别按 mineru/docling 分发到各自解析器。
- [`pdf_parser_mineru.go`](https://github.com/infiniflow/ragflow/blob/fe8dc679abee02f0ac1be7cba7f53bb64dc2fb2f/internal/parser/parser/pdf_parser_mineru.go) 配置 MinerU 服务地址，提交任务、轮询并把结果转入后续解析接口。
- [`pdf_parser_docling.go`](https://github.com/infiniflow/ragflow/blob/fe8dc679abee02f0ac1be7cba7f53bb64dc2fb2f/internal/parser/parser/pdf_parser_docling.go) 调用 Docling Serve 的 convert 接口，处理不同版本响应与分块选项。
- [`mineru.json`](https://github.com/infiniflow/ragflow/blob/fe8dc679abee02f0ac1be7cba7f53bb64dc2fb2f/conf/models/mineru.json) 有云服务配置，另有本地模型服务配置。因此“API”与“云端”不是同一概念，服务可以自托管。

**适用借鉴**：解析服务边界、任务状态、版本化响应、后续分块/索引。**不宜照搬**：已查的 Markdown 适配路径把非空文档页数设为 1，Docling 部分路径用分块数作为 pageCount；这些字段不能直接作为 SC-Wiki 的真实 PDF 页码证据。这里支持两个解析器，但源码分发不是四工具内容级融合。

## 3. GROBID + article-dataset-builder：面向文献库的数据组织

GROBID 提交：`c71ebff51e4d2a8257885458daeedede82698d43`；article-dataset-builder 提交：`920fe298a81061e8a26d55d13829ccb6deb6501c`。

- [GROBID 官方能力说明](https://github.com/grobidOrg/grobid/blob/c71ebff51e4d2a8257885458daeedede82698d43/Readme.md) 包括 header 题录、参考文献、正文引文定位与关联、姓名/机构解析、全文结构和坐标。默认 CRF 与可选深度学习模型不是同一配置，不能把最新模型指标当成本机 0.8.1 默认模型表现。
- [article-dataset-builder](https://github.com/kermitt2/article-dataset-builder/tree/920fe298a81061e8a26d55d13829ccb6deb6501c) 组织强标识（DOI/PMID 等）、开放全文获取、Crossref 等元数据、GROBID TEI、引用坐标和原 PDF，按 UUID 存本地或 S3；保留获取/解析状态，可续跑和重试。

**适用借鉴**：论文身份、题录和引用专门处理；保留原文件与结构化制品；数据可追溯且可恢复。**边界**：它不是四解析器 RAG 集成，也不替代超导物性字段提取；外部元数据应标来源，不覆盖 PDF 直接证据。

## 4. VERA：对解析质量做实际比较，引用链路单独保留

提交：`0e0d0150ef176c76a5417790c1d60fbcee983daf`。

- [`scripts/t3_parse.py`](https://github.com/PCSchmidt/VERA/blob/0e0d0150ef176c76a5417790c1d60fbcee983daf/scripts/t3_parse.py) 比较 PyMuPDF4LLM、GROBID、Docling；每工具保存正文、引用与表格输出以及耗时，正确性由单独清单判断。
- [`scripts/grobid_refs.py`](https://github.com/PCSchmidt/VERA/blob/0e0d0150ef176c76a5417790c1d60fbcee983daf/scripts/grobid_refs.py) 专门从 GROBID bibliography 提取引用记录。
- [README](https://github.com/PCSchmidt/VERA/blob/0e0d0150ef176c76a5417790c1d60fbcee983daf/README.md) 描述可核对的文献阅读、带引句综述和独立审计，并明确审计通过不保证结论正确。

**适用借鉴**：把解析器比较、引用结构化和科学语义审核分开。**边界**：这是研究型小项目，本轮没有运行它；其比较工具没有 MinerU/Marker，不能称为目标四工具组合。

## 5. Yaruk-OS：三引擎按内容路由的原型

提交：`074f948d4c2e60fb1fb34da881d7510ce725980d`。

[`router.py`](https://github.com/TYeniyayla/Yaruk-OS/blob/074f948d4c2e60fb1fb34da881d7510ce725980d/src/yaruk/core/router.py) 按表格、公式、段落等建立不同引擎链，包含 Docling/MinerU/Marker；[`merger.py`](https://github.com/TYeniyayla/Yaruk-OS/blob/074f948d4c2e60fb1fb34da881d7510ce725980d/src/yaruk/core/merger.py) 按置信度和重叠面积丢弃候选。

**适用借鉴**：按内容而不是按整篇失败来分工。**拒绝直接复用的部分**：置信度未经跨引擎标定、几何重叠不等于科学语义相同、丢弃重叠块会隐藏冲突；也没有 GROBID 的题录/引用分支。这是方案参考，不是社区主流和科学准确度证明。

## 对本项目的实际建议

采用“MinerU 全文主干 + GROBID 题录引用支路 + Docling/Marker 内容补强”，统一来源后分别导向科学数据库和知识库索引。先保留已有 MySQL/Qdrant/审核边界，不直接引入 RAGFlow 或 LightRAG 替代当前项目。若以后试接 RAG-Anything，优先验证其外部内容清单入口，避免它再次解析整篇或把概念关系写成论文引用。

这种四工具组织是针对 SC-Wiki 的设计提案，有相关工程实践支撑，但没有现成项目替我们证明准确度。需要继续验证主干配置、补强触发、跨页表格归属、冲突保留和调用成本。
