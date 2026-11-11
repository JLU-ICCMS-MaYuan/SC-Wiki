# 实施验证与当前边界

本次采用后续实施授权；先前仅文档阶段的记录保留在Git历史、原始需求及history/。共享详细记录见[#232实施验收](../232-complete-pdf-regions/implementation-validation.md)。

## 成功标准逐项核对

| 标准 | 实际证据与限制 |
| --- | --- |
| SC-001 | 多面板父整图/完整图注、真实Fig.4整图及独立面板；GPT原响应和test_pdf_regions |
| SC-002 | 不同图号/表号、截短原段落、缺图注保留unlocated；复杂未编号/扫描图注仍需原模型确认 |
| SC-003 | 300/600 DPI实际像素、矢量原页渲染及native_raster_dpi；服务端缩放限制单列 |
| SC-004 | 0/90/180/270旋转、非零CropBox、小数裁剪像素与原页对比；坐标不猜单位 |
| SC-005 | 表注/父表、跨页明确table_id、文字/公式上下文固定PDF反例；不承诺未登记跨页表自动归并 |
| SC-006 | 同参数重复/清理重建、源SHA/非法框/坏缓存拒绝、原件不改写 |

## 生产入口与覆盖

pdf_regions.py的定位/原页渲染由chart_reading.py、document_regions.py、结构原页及spectra/discovery.py实际调用。test_pdf_regions、test_image_feedback、test_issue114_storage_regions及真实Fig.4覆盖像素、图注和权限边界。

## 当前未完成门

Flash在Y-H Fig.4的科学验收仍未通过，不把6条程序候选当科研正确数据。官方OpenAI实际账号、整篇五阶段和真实提交批准不在通过范围；本地代码/Spec未push，远程文档待验证。Issue保持OPEN。完整命令、源码摘要、真实请求/响应和已知基线见共享证据目录。

## 本次MySQL与旧失败收尾

用户指向上一轮的跳过/基线说明要求“请完成”。原六项MySQL专用检查已实际执行通过；独立MySQL扩展79项零跳过，原七项失败已修正，任务专属隔离源码综合525项通过。SQLite轮的六项跳过均已由独立MySQL实跑覆盖；旧的未启用/基线结论作为首次历史记录保留，不再列为当前未完成门。详情见[#232补验收](../232-complete-pdf-regions/mysql-and-baseline-validation.md)。本轮未改生产科学字段、权限或审核规则。


## 2026-11-11 双模型黑盒排障专项

保持600DPI和原位图分辨率，跨界端点标签须有真实图框边线依据，邻面板文字不借入。原始失败、实际Flash模型重跑、字段/来源保存重读、134项回归、隔离133+1项、246表单/12变异及完整业务尚未完成边界统一见[本轮图读验证](../227-scientific-chart-reading/validation.md#2026-11-11-双模型黑盒排障专项)。不将固定回放或局部字段验收视为整篇通过。
