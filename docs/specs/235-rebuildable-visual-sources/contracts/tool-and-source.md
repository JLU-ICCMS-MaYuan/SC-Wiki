# 工具与来源契约：以PDF与版本化定位重建裁剪并供快照及RAG复用

依据：[Spec](../spec.md)与[数据模型](../data-model.md)；本契约已接入本轮代码，具体注册名与回执版本见下文和validation.md。

## 复用输入

模型提供检索命中的论文/版本及来源编号，服务端从当前授权目录解析原件与不可变定位；不能接受模型任意文件路径、用户提供URL或不属于目标的region_id。相同摘要缓存仍必须每次检查访问权限。

## 返回

结果优先提供已验证文字、数值、单位/条件及来源；需要图片时提供可重建定位、实际图片内容/授权下载能力和必要元数据。缓存命中/重建只改变计算过程，不改变来源身份和科学内容。

## 历史与清理

旧快照按照旧原件和旧定位重建，当前草稿不能覆盖。缓存缺失/损坏允许重建；原件、引用或权限错误明确返回失败。清理只处理派生缓存，不删除原件、仍引用历史或必要失败证据，不产生模型请求。

## Token与性能

记录模型调用与图片实际用量、CPU渲染耗时和缓存占用。按坐标程序裁图不计模型token；模型再次看相同图片是否命中供应商缓存取决于实际服务，不作为本Feature的节省保证。

## 当前实现接口

定位使用pdf-region-v2，逻辑region_id与物理image_cache_key分开；记录source_sha256、pdf_page、bbox_page、page_size、CropBox、rotation、dpi、renderer及父/跨页关联。image-reading-v1回执不含图片字节，实际PNG独立进入模型images参数。无新科学字段或数据库结构。

六类注册名：read_image_context、read_complete_object、adjust_image_region、recognize_image_text、digitize_image_elements、verify_image_reading。标量提取/验证接受封闭panel协议；谱线用独立report_spectrum_calibration及原谱engine，结构仍用report_structures。文字识别当前只声明原PDF文字层/已登记OCR，不冒称新部署OCR服务。

公开来源接口为GET /api/rag/visual-sources/{paper_id}及/{source_id}/image；历史来源按既有交接权限读取，不能用公开路径访问私有快照。模型图像、来源和实际用量分别留证。
