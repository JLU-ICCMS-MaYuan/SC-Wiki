# 研究与设计取舍：以可定位证据驱动同一主模型自动重读和修复

依据：[spec.md](spec.md)、[对话留档](../232-complete-pdf-regions/conversation.md)。下列为设计及外部文档调查，不是本轮代码或模型接口验收。

## 当前采用与替代历史

“检查者必须换模型”“固定最多两轮且每次DPI翻倍”“工具回执是唯一事实来源”均未采纳。后续统一由同一视觉主模型实际看图检查；保留#224每请求每轮5次传输重试，语义重读不与传输重试混用。

现行共同结论：支持图片的单一主模型；结构化回执与实际图片同时交给原模型；工具只提供实际取源/识别/计算能力。图文适用范围、首次完整图含完整图注、300/600 DPI、原PDF/定位/结果长期保存及可清理图片缓存保持。

## 决策、理由与备选

### 反馈对象

决策：以来源/回执/元素和原问题绑定动作及核验条件，记录新事实与修订版本。

理由与备选：“你算错了”不足以执行；覆盖旧回执会破坏来源恢复。

### 进展

决策：复用已有总动作预算；相同动作身份和观察摘要判断无新证据，服务故障交运行器。

理由与备选：不新增无限循环、不规定统一两轮、不把五次技术失败预算当图像科学重读轮数。

### 验证

决策：程序的几何/数值/覆盖与原模型实际像素/上下文检查共同判断；正文本身仍是来源。

理由与备选：不采用必须换检查模型、自检接近零、置信度准确率或回执唯一真值等绝对说法。

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
- `backend/ingest/image_feedback.py`：拟新增可定位反馈/动作记录/进展判断；复用图像协议，不实现另一个传输重试器。
- `backend/ingest/chart_reading.py`：把标定失败定位到元素并进入原主模型定向重读；保留目标/上下文限制区分。
- `backend/ingest/model_review.py`：字段按需查图后的具体问题反馈，普通输入/保存不触发。
- `backend/ingest/structure_reading.py`：结构读图疑点与上下文补查，保留既有几何/状态归属保护。
- `backend/ingest/model_runtime.py`：复用任务起始模型、请求/响应、工具历史和5次暂停规则。
- `backend/spectra/jobs.py`：谱线失败回执与专用数字化重算，不混入标量字段。

当前已有部分代码/测试试改出现在共享工作区，未由本次文档验证为完整交付。复杂跨页/旋转/遮挡、模型实际缩放、第三方API、真实专用字段/历史/RAG权限仍由未来测试给出结果。未选取新的部署模型或供应商，未授权软件安装/数据迁移。

## 2026-11-10 实施补充

实际目录重新核对：LLM1为deepseek-flash官方接口，LLM2为gpt-6.1-sol第三方网关；不沿用历史编号，不保存密钥。官方Flash拒绝json_schema的真实400已留证：相同严格Schema经原生report_structured_output函数传输，服务端仍验证原Schema；报告式工具使用tool_choice=required、一次一个原生调用，不能采用自由文本替代。官方OpenAI使用Responses，第三方网关保留实测Chat协议。

真实Flash曾照抄PDF点坐标为归一化框，现将发现提示统一成页面0—1000坐标，并在精读/反馈中分别声明PDF点、裁剪像素和归一化单位。程序越界、空白、柱边等问题返回具体面板/元素；错误来源不通过自动缩放猜单位。重复动作忽略措辞变化和无变化裁剪，真实无进展移除相应动作；传输重试继续复用#224。

采用来源在服务端绑定定位；交接捕获先展开已有source_ref，再冻结采用的精读及父整图；公开RAG优先批准快照，历史重建不读取新IR。派生PNG只作缓存，定位原件仍核摘要。真实效果和未完成门见validation.md。
