# 研究记录：多模态 PDF 解析与证据驱动上传 Agent

**GitHub Issue**：[ #114](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/114)

## 当前事实

- `backend/ingest/pdf_extractor.py` 使用 PyMuPDF 提取文本块，图片只写 Markdown 占位符，不把图像内容送入模型。
- `backend/ingest/upload_jobs.py` 采用分段提取、全文汇总和字段建议；草稿和 Evidence 已有稳定来源与版本边界。
- `paper_chunks`/`paper_evidences` 当前主要以页码、片段和 quote 定位，没有 bbox、表格单元或解析器版本。
- GROBID 已作为参考文献和论文结构支路使用，不替代完整页面视觉解析。
- RQ/Redis、上传任务失败收敛、旧缓存兼容和审核事务已有稳定约束。

## 决策记录

### D-001：统一适配器而不是在 Worker 中直接调用供应商

- **决定**：所有 PDF 解析器实现 `DocumentParser`，只返回合法 `DocumentIR`；Claim 候选由独立提取步骤生成。
- **理由**：隔离 Docling、MinerU、PyMuPDF 和 PDF LLM 的安装、版本和错误差异；便于测试和回退。
- **备选**：在 `upload_jobs.py` 中直接分支调用；拒绝，因为会让任务编排承担解析细节。

### D-002：Docling 默认，解析方案显式选择

- **决定**：普通数字 PDF 默认选择 Docling；复杂页面可以选择 MinerU、视觉方案或 PDF 原生多模态 LLM；PyMuPDF 作为可选文本方案。指定方案不可用时失败、重试或转人工，不静默自动切换。
- **理由**：Docling 的统一文档对象和 MIT 许可证适合作为基础；MinerU 的分层解析和视觉方案适合作为复杂样本竞争路径；显式选择能让结果质量与方案保持可审计对应。
- **备选**：解析器失败后自动降级；拒绝，因为普通文本结果可能遗漏扫描页、公式和表格，且会掩盖用户对解析质量的预期。

### D-003：PDF 原生多模态 LLM 只能作为受控适配器

- **决定**：Native PDF LLM 适配器允许模型直接读取 PDF 或页面图像，但只输出合法 `DocumentIR`；Claim 候选由独立提取步骤生成，程序必须用 IR 校验 Evidence，模型不能写库。
- **理由**：模型擅长跨页语义、图表和复杂 OCR，但长文档漏读和定位不稳定，不能承担事实写入权威。
- **备选**：整篇 PDF 一次调用直接生成最终表单；拒绝，因为无法保证覆盖、定位和 JSON 完整性。

### D-004：正式保存定位，不保存截图为事实

- **决定**：MySQL 保存文件哈希、页码、bbox/多边形、块 ID、quote、解析器和版本；通过 `paper_evidence_locators` 连接现有 `paper_evidences` 与 `paper_document_blocks`；截图从原 PDF 按需渲染。
- **理由**：支持当前 revision 的长期复核和审计，同时避免截图副本膨胀和截图与 PDF 版本漂移；旧 revision 不作为可长期打开的完整文档保留。
- **备选**：只保存页码和 quote；拒绝，因为无法支持表格单元和区域高亮。

### D-005：正确性优先，至少 50 篇基准，Shadow → 灰度 → 默认

- **决定**：新链路必须先与旧链路比较，再小范围启用，质量门通过后默认；灰度任务可以显式回到旧链路，但解析器内部不自动静默切换方案。
- **理由**：解析质量不能从工具 README 的 SOTA 声称推断，必须以超导论文标注集测量。
- **备选**：完成后直接默认；拒绝，因为真实分布外论文风险不可控。

### D-006：联网严格隔离

- **决定**：联网只返回出版元数据、研究背景和术语解释，独立标记，不进入科学 Claim。
- **理由**：避免外部论文或附件的 Tc/压力等事实混入当前上传记录；兼容 #67 的非阻塞复用。
- **备选**：联网补科学字段；拒绝，因为来源和版本匹配难以保证，且违反上传来源边界。

## 外部调研依据

- [Docling Technical Report](https://arxiv.org/abs/2408.09869)：版面分析、TableFormer、统一文档表示和本地运行能力。
- [Docling 项目](https://github.com/docling-project/docling)：支持表格、公式、OCR、VLM、MCP 和区域结构；本项目不直接采信其自报准确率。
- [MinerU 技术报告](https://arxiv.org/abs/2409.18839)：PDF-Extract-Kit 和高精度文档内容抽取。
- [MinerU2.5](https://arxiv.org/abs/2509.22186)：全局版面分析与局部高分辨率识别的两阶段思路。
- [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR)：文档 OCR、表格、公式和图表视觉解析；本 Feature 首期不把它作为基础解析器。
- [olmOCR-Bench](https://github.com/allenai/olmocr)：约 1,400 篇文档和 7,000 多个测试用例的 OCR/PDF 评测思路，可借鉴其类别划分。
- [GROBID](https://github.com/grobidOrg/grobid)：科学论文元数据、章节、参考文献和坐标抽取，继续作为专用支路。
- [Lost in the Middle](https://arxiv.org/abs/2307.03172)：长输入位置效应，支持覆盖审计和分区阅读的必要性。

## 许可证和部署注意

Docling 为 MIT；PaddleOCR 为 Apache-2.0；MinerU 使用 Apache-2.0 加附加条款，实际部署前需将其许可证随依赖清单和发布镜像一起核对。Docling/MinerU 可以有 CPU 路径，但复杂视觉模型需要更高资源；本 Feature 不把 GPU 作为服务启动条件。

## 未决但不阻塞事项

- 具体 PDF LLM 供应商由现有 LLM 配置和能力探测决定，不在本 Feature 固定厂商。
- 50 篇论文标注集的来源和标注工具需在 T002 中登记，未登记前不能宣布质量门通过。

## 2026-09-24：真实版本适配与安装核验

本轮落实 FR-001～FR-004、FR-010 对应 T010/T011：解析器只输出 IR，独立进程
运行供应商 SDK，超时终止进程组；无法解析时返回稳定错误，不调用其他解析器。

- Docling 2.130.0 的分发包依赖 `docling-slim[standard]`，使用 `DocumentConverter`
  和 `PdfPipelineOptions`。`layout` 明确走 CPU、文本层与表格结构，不启用 OCR
  或远端服务；公式/图像项保留类型，未识别的图像内容不视为已读取。
- MinerU 4.0.6 使用公开 `parse(path, tier, ocr_mode, ...)`，并输出 DocVortex
  Middle JSON；旧版 pipeline API 不适用于本次锁定版本。`ocr` 使用 `basic/ocr`；
  适配器级选项可显式指定 `flash/basic/standard/advanced` 和 `txt/ocr`，不自动换档。
  `flash/txt` 的数字 PDF 成功不能作为 OCR 验收。standard/advanced 尚未完成真实模型验收。
- Docling bbox 按原点转换为左上原点 PDF 点坐标；MinerU 4 bbox 为 0～1 归一化值，
  乘原 PDF 页面尺寸。表格 HTML 没有单元格 bbox 时仅保存行列和跨度，并记录限制。
- 数据块稳定键包含文件身份、哈希、解析器版本、方案、页码与顺序；数据库运行身份
  仍独立管理，不把随机运行编号放入内容哈希。
- 项目 Conda `sc-wiki`（Python 3.12.14）安装了 Docling 2.130.0、MinerU 4.0.6、
  PyTorch 2.10.0+cpu；保留 NumPy 1.26.4，由依赖求解选择 OpenCV 4.11.0.86。
  `pip check` 通过。另建隔离环境先行验证；未升级数据库、重启服务或开启默认新链路。
- Hugging Face 直连失败，镜像下载最初遇到 Xet 401；测试进程使用
  `HF_ENDPOINT=https://hf-mirror.com`、`HF_HUB_DISABLE_XET=1` 下载相同模型。
  该设置没有写入系统或应用环境配置。下载可用不等于所有目标部署环境可用。

许可证依据为已下载 wheel 的 METADATA 和随包 LICENSE：Docling 为 MIT；MinerU
声明 `LicenseRef-MinerU-Open-Source-License`，含 Apache-2.0 及附加条款：在线服务需
显著注明使用 MinerU，合并月活超过一亿或月收入超过两千万美元需要单独商业许可。
根 README 已增加归因。模型权重许可及完整 Docker 镜像仍需分别核验，T001 不据此全部完成。

## 2026-09-24：评测报告可复核性

SC-001～SC-003 / T002、T030、T031 对应 `pdf_benchmark.py` 与默认门。标注用文件
摘要和归一化区域，不依赖解析器块 ID。科学记录与条件一对一精确匹配，区域要求
同源、同页、同引句且 IoU≥0.5，避免重复输出加分或整页大框冒充精确定位。
单位、字段和条件规范化由固定导出契约承担，不调用模型判断同义词。

失败或缺失论文保留分母，三个复杂类别分别提升；仅接受附逐论文计数、输入摘要和
独立验收引用的版本 1 报告。合成集不能开启默认门，正式写入、失败恢复和审核兼容
仍由独立验收证明。离线比较与完整上传运行驱动分开，后者仍待实现。
