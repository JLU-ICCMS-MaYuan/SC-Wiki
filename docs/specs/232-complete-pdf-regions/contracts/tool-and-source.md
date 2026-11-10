# 工具与来源契约：可靠定位PDF区域并生成含完整图注的高清裁剪

依据：[Spec](../spec.md)与[数据模型](../data-model.md)；本契约已接入本轮代码，具体注册名与回执版本见下文和validation.md。

## 输入与输出

输入是当前来源的文件/页/区域身份及对象类型；局部请求引用已有父区域，可提出具体范围和清晰度需求。输出是完整定位描述、图片/有序分片及完整性结果。首次图的主体框与图注框分别保留，同时返回实际包含二者的完整裁剪。

## 边界和失败

非法页码、越界、零宽、非有限坐标或原件摘要不符拒绝。缺图注、配对不唯一、图形被切断、低清位图、复杂跨页未验证均有定位原因。可以回原页/重定位取得新依据，不能因图片文件成功生成就声明完整。

## 消费方

#233传递图像与事实，#234提交定向修正，#235保存不可变定位并重建。所有消费者必须使用同一图像变换；侧栏标记单独叠加，不能污染干净图。

## 当前实现接口

定位使用pdf-region-v2，逻辑region_id与物理image_cache_key分开；记录source_sha256、pdf_page、bbox_page、page_size、CropBox、rotation、dpi、renderer及父/跨页关联。image-reading-v1回执不含图片字节，实际PNG独立进入模型images参数。无新科学字段或数据库结构。

六类注册名：read_image_context、read_complete_object、adjust_image_region、recognize_image_text、digitize_image_elements、verify_image_reading。标量提取/验证接受封闭panel协议；谱线用独立report_spectrum_calibration及原谱engine，结构仍用report_structures。文字识别当前只声明原PDF文字层/已登记OCR，不冒称新部署OCR服务。

公开来源接口为GET /api/rag/visual-sources/{paper_id}及/{source_id}/image；历史来源按既有交接权限读取，不能用公开路径访问私有快照。模型图像、来源和实际用量分别留证。
