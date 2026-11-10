# 数据模型与所有权：可靠定位PDF区域并生成含完整图注的高清裁剪

依据：[spec.md](spec.md)、[接口契约](contracts/tool-and-source.md)。本文件记录已实施内部协议，不新增科学标准字段。

### 区域定位

内部来源协议保存`region_id`、对象类型、原文件内容摘要、PDF页、页面尺寸、旋转、CropBox、坐标空间、主体区域、完整图注区域、合并裁剪区域、父区域和定位版本。图号是论文标签，`region_id`是程序身份，不能混用。跨页对象使用有序的原页区域列表，不能把多页坐标写进单页框。

### 图像与坐标

定位采用浮点页面坐标，模型归一化坐标只作传输表示；必须保存变换方向与参考图片。图像观察包含实际宽高、请求DPI、原始位图像素/有效分辨率、图像内容摘要、渲染器及版本。像素取整边界根据真实输出计算，不只用宽高比例推断。

### 完整性

图注配对、全部面板、刻度、图例、标签分别有可说明的结果和限制。`located`只表示定位，不自动等于科学正确；图注未定位不能写“首次完整裁图已通过”。区域信息进入#235共享来源，图片字节只进入可清理缓存。

## 当前实现接口

定位使用pdf-region-v2，逻辑region_id与物理image_cache_key分开；记录source_sha256、pdf_page、bbox_page、page_size、CropBox、rotation、dpi、renderer及父/跨页关联。image-reading-v1回执不含图片字节，实际PNG独立进入模型images参数。无新科学字段或数据库结构。

六类注册名：read_image_context、read_complete_object、adjust_image_region、recognize_image_text、digitize_image_elements、verify_image_reading。标量提取/验证接受封闭panel协议；谱线用独立report_spectrum_calibration及原谱engine，结构仍用report_structures。文字识别当前只声明原PDF文字层/已登记OCR，不冒称新部署OCR服务。

公开来源接口为GET /api/rag/visual-sources/{paper_id}及/{source_id}/image；历史来源按既有交接权限读取，不能用公开路径访问私有快照。模型图像、来源和实际用量分别留证。
