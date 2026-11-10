# 研究与设计取舍：以PDF与版本化定位重建裁剪并供快照及RAG复用

依据：[spec.md](spec.md)、[对话留档](../232-complete-pdf-regions/conversation.md)。下列为设计及外部文档调查，不是本轮代码或模型接口验收。

## 当前采用与替代历史

用户先希望提交后永久保存采用的PNG，后考虑快照体积，明确认可“原PDF＋定位＋解析结果长期保存，图片按需重建并缓存”。后一方案替代前一方案；首次裁剪含完整图注和历史来源可追溯仍保留。

现行共同结论：支持图片的单一主模型；结构化回执与实际图片同时交给原模型；工具只提供实际取源/识别/计算能力。图文适用范围、首次完整图含完整图注、300/600 DPI、原PDF/定位/结果长期保存及可清理图片缓存保持。

## 决策、理由与备选

### 存储

决策：原PDF＋不可变定位＋解析结果长期保存，PNG内容寻址缓存可重建；快照只引用。

理由与备选：永久保留每张采用PNG增加体积，已由用户后续要求替代。

### 历史

决策：采用时冻结原文件/区域/变换/渲染约定，旧快照不引用最新定位。

理由与备选：只有paper_id/page而没有版本与框不能准确重建历史；渲染库升级不得默默改变已声明的一致性。

### RAG

决策：先检索已有可用结果和精确来源，必要时按权限定位重建；元数据不携带任意路径。

理由与备选：每问一次都调用模型重新找图既耗token又可能改变位置，缓存命中也不能跳过权限。

## 官方资料与调查边界

| 材料 | 支持的结论与限制 |
| --- | --- |
| [DeepSeek模型表](https://api-docs.deepseek.com/quick_start/pricing) | 2026-11-10读取：deepseek-flash映射DeepSeek-V4.1-Flash-1017并支持Vision；deepseek-v4-pro不支持。适用官方服务，不推断所有网关。 |
| [DeepSeek视觉接口](https://api-docs.deepseek.com/guides/vision) | 2026-11-10读取：支持图片及图表，Chat Completions/Responses字段不同；大图自动缩放到约1300×1300像素量，600 DPI文件仍可能需要局部精读。 |
| [DeepSeek版本发布](https://api-docs.deepseek.com/news/news261017) | 2026-11-10读取：V4.1-Flash-1017发布并提及对WorkBuddy/CodeBuddy优化；不能据此断言WorkBuddy内部工具如何传图。 |
| [GPT-6.1 sol官方模型页](https://developers.openai.com/api/docs/models/gpt-6.1-sol) | 2026-11-10读取：支持Text/Image输入，工具调用要求Responses API。当前本机LLM2第三方网关的实际能力尚未实测。 |
| [PaddleOCR结果结构](https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/pipeline_usage/OCR.en.md) | 可提供rec_texts/rec_boxes/rec_polys/rec_scores等文字、位置和识别分数；分数不等于科学准确率。 |
| [PyMuPDF绘图提取](https://pymupdf.readthedocs.io/en/latest/recipes-drawing-and-graphics.html) | get_drawings可提供线/曲线/矩形/颜色及位置；返回路径不自动证明可见元素或科学语义。 |
| [pdffigures2](https://github.com/allenai/pdffigures2) | 主要定位有图注图表；图注构建、候选框、正文约束、切断/重叠评分值得借鉴，领域与复杂版式边界需真实验证。 |
| [PP-Chart2Table](https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/module_usage/chart_parsing.en.md) | 官方示例返回图表转文字表，不保证具备本方案全部像素标定事实。未选择其作为必须部署依赖。 |

本机只读配置调查在本次侧边对话中曾确认LLM1为deepseek-v4-pro、LLM2为gpt-6.1-sol（第三方网关）、LLM3为deepseek-flash（官方端点）。这些是当时配置事实，不固定未来编号，也不在文档保存密钥/完整私有端点。未进行本轮付费模型请求，官方声明与实际网关效果仍须分开验证。

## WorkBuddy建议的采用边界

采用可定位回执、原图像素复核、程序标定、元素级失败原因与定向动作、版本留存。拒绝“自然语言绝对不可校验”“自检检出率接近0”“必须换模型”“固定两轮/DPI翻倍”“回执唯一真值”的绝对结论。换裁剪不自动构成独立正确证据，置信度也不等于科学准确率。

数字标签是原图报告值，可以识别后核验；坐标/色标估读由程序算并保留约数与精度；其他原文/表格证据有效。正文已知值不能无条件反推图轴，否则可能把应保留的分歧强行消掉。读图能力探针不证明整篇准确率。

## 代码调查与未知项
- `backend/ingest/pdf_regions.py`：与#232共享定位/渲染模块，补内容寻址可清理缓存；不复制另一套裁图。
- `backend/ingest/document_storage.py`：正式来源及IR元数据保存/重读，关联采用的不可变定位。
- `backend/ingest/field_sources.py`：复用已有共享上下文/来源目录，避免快照整包复制。
- `backend/services/manuscript_handoffs.py`：快照保留原件引用和定位版本，原件沿已有摘要存储。
- `backend/ingest/document_regions.py`：当前来源和历史来源按各自授权与定位重建。
- `backend/rag/agent/tools.py`：对已批准来源提供查结果/按定位取图的问答工具，模型不自行提供文件路径。
- `backend/rag/tools/chroma.py`：保留语义检索的精确来源关联，避免只按paper_id丢失目标片段。
- `backend/api/rag.py`：复用现有API/权限，按需提供来源区域或下载，不暴露缓存目录。

当前已有部分代码/测试试改出现在共享工作区，未由本次文档验证为完整交付。复杂跨页/旋转/遮挡、模型实际缩放、第三方API、真实专用字段/历史/RAG权限仍由未来测试给出结果。未选取新的部署模型或供应商，未授权软件安装/数据迁移。

## 2026-11-10 实施补充

实际目录重新核对：LLM1为deepseek-flash官方接口，LLM2为gpt-6.1-sol第三方网关；不沿用历史编号，不保存密钥。官方Flash拒绝json_schema的真实400已留证：相同严格Schema经原生report_structured_output函数传输，服务端仍验证原Schema；报告式工具使用tool_choice=required、一次一个原生调用，不能采用自由文本替代。官方OpenAI使用Responses，第三方网关保留实测Chat协议。

真实Flash曾照抄PDF点坐标为归一化框，现将发现提示统一成页面0—1000坐标，并在精读/反馈中分别声明PDF点、裁剪像素和归一化单位。程序越界、空白、柱边等问题返回具体面板/元素；错误来源不通过自动缩放猜单位。重复动作忽略措辞变化和无变化裁剪，真实无进展移除相应动作；传输重试继续复用#224。

采用来源在服务端绑定定位；交接捕获先展开已有source_ref，再冻结采用的精读及父整图；公开RAG优先批准快照，历史重建不读取新IR。派生PNG只作缓存，定位原件仍核摘要。真实效果和未完成门见validation.md。
