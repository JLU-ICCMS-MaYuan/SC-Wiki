# 研究与设计取舍：统一固定视觉主模型的看图工具回执与实际图片传递

依据：[spec.md](spec.md)、[对话留档](../232-complete-pdf-regions/conversation.md)。下列为设计及外部文档调查，不是本轮代码或模型接口验收。

## 当前采用与替代历史

早期纯文本/视觉双路线及独立视觉后端的提议已撤回。后续官方资料确认DeepSeek Flash和GPT-6.1 sol支持图片，用户明确取消纯文本路线并暂不部署Qwen3-VL。原话中“GPT-6o”按原文保留，当前已核实型号是gpt-6.1-sol，不自行改写型号。

现行共同结论：支持图片的单一主模型；结构化回执与实际图片同时交给原模型；工具只提供实际取源/识别/计算能力。图文适用范围、首次完整图含完整图注、300/600 DPI、原PDF/定位/结果长期保存及可清理图片缓存保持。

## 决策、理由与备选

### 角色

决策：只有任务起始选定的视觉主模型，读取工具返回和原图后补充观察；工具负责取源、裁剪、OCR/像素和计算。

理由与备选：撤回文本主模型分支、第二视觉后端和Qwen3-VL前置部署。

### 传输

决策：业务层统一回执和图片清单，适配层按实际Chat Completions/Responses协议装配；工具历史保留编号配对。

理由与备选：模型名字支持图片不等于网关/协议已实测，不用未知字段猜接口兼容。

### 六类动作

决策：复用read_document/read_page/read_region/extract_table/inspect_figure等并补足图像动作；参数由程序限定，工具只暴露实际能力。

理由与备选：自然语言说“换方法”却没有实际操作不算反馈成功，也不允许任意shell脚本。

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
- `backend/ingest/image_reading.py`：拟新增统一工具回执/图片交接层，复用原主模型与来源，不是独立视觉模型服务。
- `backend/ingest/review_tool_contract.py`：六类动作与现有来源工具的封闭定义和可用能力目录。
- `backend/rag/llm.py`：保留统一模型入口，按实际接口适配图像与严格工具调用，记录模型身份和用量。
- `backend/rag/llm_context.py`：沿用任务起始配置；不新增第二个生成模型配置槽。
- `backend/ingest/model_review.py`：按需查图与收到图片的核对循环。
- `backend/ingest/structure_reading.py`：结构识读接统一图像交接，几何解码和归属职责保持。
- `backend/spectra/vision.py`：谱标定使用同一视觉主模型及实际图像，不另选模型。
- `backend/spectra/discovery.py`：将图例/轴/曲线观察交后续确定性数字化。

当前已有部分代码/测试试改出现在共享工作区，未由本次文档验证为完整交付。复杂跨页/旋转/遮挡、模型实际缩放、第三方API、真实专用字段/历史/RAG权限仍由未来测试给出结果。未选取新的部署模型或供应商，未授权软件安装/数据迁移。
