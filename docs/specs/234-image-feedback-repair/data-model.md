# 数据模型与所有权：以可定位证据驱动同一主模型自动重读和修复

依据：[spec.md](spec.md)、[接口契约](contracts/tool-and-source.md)。本文件记录已实施内部协议，不新增科学标准字段。

### 问题与动作

问题包含来源、区域、元素、原回执、具体疑点/原因、已读上下文和验收条件；动作包含封闭类别与已验证参数，引用问题和父区域。动作身份按来源版本、目标、方法和参数生成，相同问题下相同观察不自动算进展。

### 修订与采用

新回执引用父回执和实际图像摘要，保留旧结果/来源。当前采用版本通过程序与既有科学核对决定，不能由“新版”标志或模型自述决定。无关点、材料状态、方法和μ*记录保留稳定身份。

### 恢复状态

复用#224运行器，检查点含原主模型、问题、工具调用编号/返回、图像定位、完整响应及已完成记录；不新建第二套模型或重试计数。临时失败、固定接口错误、科学疑点、真实来源缺失是不同结果。缓存可消失但原定位/原件/必要失败证据不可丢。

## 当前实现接口

定位使用pdf-region-v2，逻辑region_id与物理image_cache_key分开；记录source_sha256、pdf_page、bbox_page、page_size、CropBox、rotation、dpi、renderer及父/跨页关联。image-reading-v1回执不含图片字节，实际PNG独立进入模型images参数。无新科学字段或数据库结构。

六类注册名：read_image_context、read_complete_object、adjust_image_region、recognize_image_text、digitize_image_elements、verify_image_reading。标量提取/验证接受封闭panel协议；谱线用独立report_spectrum_calibration及原谱engine，结构仍用report_structures。文字识别当前只声明原PDF文字层/已登记OCR，不冒称新部署OCR服务。

公开来源接口为GET /api/rag/visual-sources/{paper_id}及/{source_id}/image；历史来源按既有交接权限读取，不能用公开路径访问私有快照。模型图像、来源和实际用量分别留证。


## 前置盘点与几何观察

盘点纠错沿原discovery_schema，只有当前错误页重问；被拒绝观察标明非原文，额外整图/图注记录原件/定位/图像SHA和全页归一化坐标。已合法页及失败历史保留。

image-geometry-v1只记录当前图的无标签框、刻度候选、色块、分析分辨率和像素摘要。分析副本最多2000像素边长，原模型图片和300/600 DPI原件不缩小；候选可含图例，灰色/超预览范围明确限制，不把缺候选当无数据。动作缓存包含几何版本；回执/区域/原件身份沿既有协议。没有新科学表单键或自动采纳。
