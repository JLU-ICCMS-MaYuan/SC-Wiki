# 数据模型与所有权：以PDF与版本化定位重建裁剪并供快照及RAG复用

依据：[spec.md](spec.md)、[接口契约](contracts/tool-and-source.md)。本文件记录已实施内部协议，不新增科学标准字段。

### 权威数据与缓存

现有原件和共享来源目录保存原件摘要/版本、采用定位及解析事实。`locator_digest`标识不可变内容，引用需保留原文件谱系；上传file_id转正式ID由服务端映射，不因临时ID变化丢失原摘要/页/框。权限仍以当前访问目标核验，摘要本身不是授权凭证。

### 缓存键

由原PDF摘要、定位版本、实际框/坐标空间、DPI、渲染器/版本与必要处理参数生成。持久参数无base64；PNG和校验回执位于可清理缓存，原子写入，损坏可重建。模型提示词和问题变化不应重新渲染相同图像。

### 快照

快照冻结采用的定位和结果引用，不冻结整包运行中图片；仍保留必要原文件。原件与科学证据不可清理。重建一致性要求同一原件与语义区域，不无条件承诺不同渲染库下PNG逐字节相同；发现渲染版本不兼容时明确处理并留记录。

### 问答来源

检索结果保留论文批准版本、文件/页/块/区域身份和解析事实；模型可取得当前授权版本的区域，公开路径仅批准来源。历史查看另走现有快照权限，不能通过公开RAG读取私有历史。

## 当前实现接口

定位使用pdf-region-v2，逻辑region_id与物理image_cache_key分开；记录source_sha256、pdf_page、bbox_page、page_size、CropBox、rotation、dpi、renderer及父/跨页关联。image-reading-v1回执不含图片字节，实际PNG独立进入模型images参数。无新科学字段或数据库结构。

六类注册名：read_image_context、read_complete_object、adjust_image_region、recognize_image_text、digitize_image_elements、verify_image_reading。标量提取/验证接受封闭panel协议；谱线用独立report_spectrum_calibration及原谱engine，结构仍用report_structures。文字识别当前只声明原PDF文字层/已登记OCR，不冒称新部署OCR服务。

公开来源接口为GET /api/rag/visual-sources/{paper_id}及/{source_id}/image；历史来源按既有交接权限读取，不能用公开路径访问私有快照。模型图像、来源和实际用量分别留证。
