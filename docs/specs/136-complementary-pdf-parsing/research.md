# 三引擎互补解析前置调研

日期：2026-10-13。关联 [Spec 草案](spec.md) 与 [Issue #136](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/136)。

本文保留进入设计前的事实核查和候选分析；后续真实六次解析及四路表单结果见 [验证记录](validation.md)，不要把前置调研时的“尚未运行”与后续实际结果混用。

## 当前结论

1. 没有足够证据支持“社区最常用的 MinerU + Docling + Marker 组合”这一说法。检索到的具体实践包括单引擎路由、并排基准，以及按内容分配不同引擎；未发现可直接证明 SC-Wiki 全字段准确度的成熟组合。
2. 可借鉴“按内容分工、统一内容结构、保留来源”的方法，但不能直接采用按重叠面积和引擎置信度删除候选的合并逻辑。不同解析器的置信度并未在本项目标定，且区域重叠不证明科学内容等价。
3. H3S 旧实验已经显示具体互补机会：Docling 保留表格列和单元定位，MinerU 修复部分负号、乘号和数学符号。旧实验没有 Marker，也没有证明新的互补方案有效。
4. 当前官方文档已经涉及 MinerU 4.x 与 Marker 2.x。不能照搬早期 Marker/Surya 运行经验，也不能把上游主分支能力当作本机已安装版本能力。

## 本机和输入核验

工作分支为 `mayuan`，读取代码时 HEAD 为 `5b4d4ed88656ff171f90e45ff1eb1da10e3d8c30`。工作树包含 #120/#135 等既有未提交更改，因此 HEAD 不是当前提取契约的完整快照；后续实际运行须额外保存使用文件摘要和差异清单。

操作系统：macOS 26.5.1 / arm64。项目 Python 环境：`/Users/mayuan/software/miniconda3/envs/sc-wiki/bin/python`。通过 `importlib.metadata.version` 读取：

| 依赖 | 本机版本 | 本轮核验范围 |
| --- | --- | --- |
| Docling | 2.130.0 | 已安装，未重跑解析 |
| MinerU | 4.0.6 | 已安装，未重跑解析 |
| Marker / marker-pdf | 未安装 | 尚无本机执行证据 |
| Surya / surya-ocr | 未安装 | 不推定 Marker 模型已就绪 |
| PyTorch | 2.14.0 | 元数据读取，未测加速能力 |
| PyMuPDF | 1.28.2 | 已打开输入并读取页数及首页 |

输入根路径：`.data/upload_PDFs/947214683efc415abd9b1d64c457d86c/`。

| 角色 | 当前文件名 | 页数 | SHA-256 |
| --- | --- | ---: | --- |
| 正文 | `103e9de9802e41e397429b8b801c89d8.pdf` | 6 | `22ebd3113ca0cd514ee1c92d3d22e7da5374f2ba682f582350f5b10508d379ef` |
| 补充 | `8c30c34dc56d45afa6e153aa999eb0d1.pdf` | 10 | `2c04b51e2cb57259fe8f8e5c8a464871647b5a0a7a731ee636f42cc406efb396` |

两份首页标题均为 Pressure-induced metallization of dense (H2S)2H2 with high-Tc superconductivity；补充首页明确标识 Supplementary information。哈希与 [2026-09-24 案例记录](../114-multimodal-pdf-upload-agent/case-studies/2014-h3s.md) 完全一致，原 PDF 未改写。本机旧 `issue114-h3s-2014-*` 实验目录本轮未找到，旧报告中的运行结论只作为历史记录。

## 上游官方证据

通过 GitHub API 实时读取 README、发行版与提交；下列源码链接固定到本轮查询的提交，避免以后将文档漂移误作本轮证据。上游说明是其能力声明，不等于本机实测。

| 引擎 | 已查证的上游说明 | 适用边界与后续核验 |
| --- | --- | --- |
| [Docling](https://github.com/docling-project/docling/blob/f0d90989b461656102da5d449db98e6be9285f93/README.md) | 支持阅读顺序、表格结构、公式、图片分类和统一 DoclingDocument；可导出无损 JSON，支持本地执行 | 本项目 `pdf_parser_worker.py` 实际设定 `do_ocr=False`、`do_table_structure=True`、CPU、禁止远端服务；不能把上游可选 OCR/VLM 能力算成本机当前路径已启用 |
| [MinerU](https://github.com/opendatalab/MinerU/blob/b7f3dd0c5f6e6d66a298239ffd02b328b873918e/README.md) | 4.x 提供 flash/basic/standard/advanced，不同层级与小模型/VLM 运行时组合；保留结构化内容和文档定位 | 当前适配器固定使用配置指定的 tier，默认 basic OCR，`image_analysis=False`；不能称其已完成图中数据提取，不能以升级版文档证明 4.0.6 行为 |
| [Marker](https://github.com/datalab-to/marker/blob/e7c67f1d239ea6a805cbf4ed6c6b2056d435e22d/README.md) | 2.x 的 fast/balanced 路径结合 PDF 文本层、布局、Surya VLM 和表格重建；支持 JSON、图片与分页输出 | 引擎内部 VLM 与额外 `--use_llm` 后处理是不同层次；后者会额外修改表格、行内公式等。三路基线不能只给 Marker 额外模型修订而不记录 |

GitHub 最新发行版查询结果：Docling `v2.138.0`（2026-10-12）、MinerU `mineru-4.0.12-released`（2026-10-11）、Marker `v2.0.0`（2026-07-20）。这只是本轮查询值，不是已安装清单或本项目升级决定。另读取 [Marker v2.0.0 README](https://github.com/datalab-to/marker/blob/v2.0.0/README.md)，确认其也包含上述模式和本地推理服务路径。

Marker 当前说明中，CPU/Apple Silicon 路径依赖 llama.cpp 推理服务，NVIDIA 路径使用 vLLM；因此安装 Python 包不等于真实运行完成。Docling 代码为 MIT；Marker 当前代码为 Apache-2.0，模型权重另有修改版 AI Pubs Open Rail-M 条款。模型与代码许可证需按实际锁定制品分别记录，不能沿用旧版本“Marker 全部 AGPL”的泛化结论。MinerU 的实际发行包、模型与附加条款也需在锁定环境时核对；本轮没有完成生产部署许可证验收。

## 社区组合实践

检索命令包括 `gh search repos "mineru docling marker"`、`"docling marker"`、`"mineru docling"` 以及三者同现的 Issue 搜索；仓库检索受关键词和返回数量限制，不是社区普及度调查。星标数只描述本轮样本，不能证明效果。

| 案例 | 核查内容 | 可借鉴与不可直接复用之处 |
| --- | --- | --- |
| [Yaruk-OS](https://github.com/TYeniyayla/Yaruk-OS/tree/074f948d4c2e60fb1fb34da881d7510ce725980d) | README、`src/yaruk/core/router.py`、`merger.py`、`orchestrator.py`；本轮查询为 0 星 | 路由按段落/表格/公式/图像区分引擎，可借鉴内容分工与统一结构。默认表格链 Docling→MinerU→Marker，公式链 MinerU→Marker→Docling，但它同时存在失败/低置信度回退；不是本项目要求的完整答案 |
| [pdf-ingest-skill](https://github.com/danmackinlay/pdf-ingest-skill/tree/6ca415679ee65854f2003c004bd9df15b07b8b76) | README；本轮查询为 2 星 | 强调本地、Apple Silicon、资源预算及选一个足够好的引擎，适合参考环境隔离；不提供本需求的三路科学字段冲突审计 |
| [pdf-to-md-bench](https://github.com/wyh020612/pdf-to-md-bench/tree/167432cd5aab74f58372b5b437b9f7d429bfc17a) | README；本轮查询为 2 星，声称 5 份 PDF、6 工具、30 次测量 | 可借鉴一致输入与比较口径。其 Surya 0.17/MPS 故障和评分属于该版本及案例，不能直接推断当前 Marker 2.x 会失败 |
| [rag-api](https://github.com/BukeLy/rag-api/tree/f7e2565a6faa09c79be1148c9087ba34841ae066) | README；本轮查询为 65 星 | 组合的是 DeepSeek-OCR/MinerU/Docling，并提供多种模式；不是 MinerU/Docling/Marker 的唯一默认互补方案 |

Yaruk-OS 的 `merger.py::_dedup` 先按 confidence 降序排序，再对同页 IoU > 0.8 的块只保留先出现者，没有比较科学值；注释称跨 provider 去重，但实现也未检查 provider 是否不同。`_reassign_reading_order` 再按页面、y、x 排序。这些规则会丢弃重叠候选，且排序不能单独证明双栏阅读顺序正确，不适合作为本项目科学来源的直接合并规则。本轮未运行或独立验证该社区项目。

## 本项目历史实测与当前契约

[2026-09-28 H3S 报告](../114-multimodal-pdf-upload-agent/case-studies/2014-h3s-codex-20260928.md) 使用的是 PyMuPDF、Docling、MinerU，不能替代本轮要求的 MinerU、Docling、Marker 三路。历史记录显示：

- Docling 的表格单元定位更细；MinerU 有局部合列、H3S 化学式误读和 Wyckoff 字母误读。
- MinerU 曾更好地恢复负号和 k/q 网格乘号。17 项指定检查的较好结果不等于整张表准确率。
- 定位检查曾接受“Tc=999 K 引用真实 Tc 段落”等错误候选，证明来源定位与语义核对必须分开。
- 旧领域提示、枚举、化学式归一化曾有共同错误。当前文件已变化，不能直接称这些问题今天仍未修复。

当前应复用的事实来源：

| 文件 | 读取到的职责 | 本轮发现 |
| --- | --- | --- |
| `backend/ingest/document_ir.py` | 文件、页面、内容块、表格单元、图像、公式的统一结构 | 可供三路来源映射；缺少单元坐标时不得编造 |
| `backend/ingest/document_parsers.py` | 解析器协议、注册和运行记录 | 现有 Docling/MinerU/PyMuPDF；尚无 Marker 适配器 |
| `backend/ingest/structured_pdf.py` | 子进程调用和上游结构到 IR 的转换 | 当前丢弃子进程 stdout/stderr，临时原始响应会清理；真实 demo 需要另外留存原始结果与诊断，不能仅保存转换后的 IR |
| `backend/ingest/pdf_parser_worker.py` | 实际 Docling/MinerU 调用配置 | 能力受配置约束，不能据上游产品说明推断已启用能力 |
| `backend/ingest/domain_extraction.py` | 版本 1 领域输出、规范化及科学候选合并 | 有工作树修改；不能仅记录 HEAD 复现本次运行 |
| `backend/ingest/upload_contracts.py` | 版本 2 草稿与物性记录输入 | 有工作树修改；材料状态与记录条件需保持现有归属 |
| `backend/data/form_definitions.v1.json`、`backend/ingest/form_definitions.py` | 内置表单定义与定义校验 | JSON 文件 SHA-256 为 `c3bad156bbb778481aa7eb65806731139aaee65efc133a5badc02fcb18fbbe34`；不能据内置文件推定数据库当前发布定义完全一致 |

现有 [表单映射](../../overview/01_Decentralized_Uploading_of_Superconductivity_Data/data-structure-and-form-mapping.md) 覆盖论文信息、材料状态、结构候选、物性模块、逐记录条件和证据。HTML 不能只做 Tc 数值排行，也不能把解析出来但现有契约不支持的性质偷偷塞成新字段。

## 待实测候选与备选分析

以下为 AI 技术候选，待 Spec 确认后进入正式设计并用数据选择，不是预先固定赢家：

- 以 Docling 的结构化表格及定位作为表格对齐候选，以 MinerU 的公式/OCR 结果补充数学符号候选，以 Marker 的独立布局、阅读顺序和数学内容结果提供额外候选。每类都须允许其出错，不能形成全局“引擎 A 永远覆盖 B”的规则。
- 先通过真实三路全量输出建立对照，再验证内容需求触发的互补策略。demo 为了测量而运行三路，不代表生产中每页永远三次解析；评估时也不能让“按需策略”偷看本来未调用引擎的答案。
- 参考答案和核对清单只参与评测；不能把旧 H3S 参考表喂给生成模型，再称新算法找到了这些数值。
- 解析、来源对齐、科学提取、表单校验、人工核对分别保留结果。不能用模型长文本拼接替代单元格结构，也不能为了契约通过删除难以表达的原始候选。

不采用的直接替代方案：整篇失败后轮流切换引擎（不满足内容互补）、三份 Markdown 全量拼接后只留一个回答（冲突和出处容易消失）、按引擎多数票判科学正确（相关错误可能一致）、直接安装整个社区编排系统（与现有 IR/表单重复，且未满足科学冲突保留要求）。

## 未决与验证边界

本轮已完成源文档阅读、输入身份核实、依赖盘点和 Spec 草案；未完成 Marker 安装/模型准备、三引擎重跑、同一下游模型提取、内容互补算法、HTML 或人工科学核对。具体模型与运行预算在执行前从现有配置核实，报告仅保留非敏感参数。原始比较图缺失已登记；公开调研不依赖其排名，图片归档仍未通过。

下一阶段需在确认本版 Spec 后建立 Plan、数据模型、接口契约、Tasks 和可执行 quickstart；此处不以未经确认的任务清单替代该阶段门。遵循 KISS/DRY：优先复用现有 IR 与表单契约；遵循 YAGNI：首阶段只建设独立 demo，不增加数据库实体或产品解析选项。

## 已确认基线后的实际设计与取舍

用户“继续！”确认后已建立 Plan/数据模型/接口/Tasks 并实施。采用按内容触发的空间候选组合，保留全部原始输出和不确定对应；只省去重复元数据，不改写科学数值。Marker 使用独立 2.0.0 环境与本地模型，额外云端修订关闭；四路共用 deepseek-v4-pro 的相同提示和预算，明确关闭额外推理。

实际结果否定了“加更多候选就会更准确”的预期：互补输入扩大至约 14 万 token，并出现压力错挂。保留这次负面结果作为下一轮设计依据，不为了得到正面结论替换最终比较中的某一路回答。当前通用架构仍只用于实验；生产内容路由的调度、裁决粒度及条件归属约束尚待改进与重新验收。
