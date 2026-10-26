# 数据模型

## 本机 Demo 文档

- schemaVersion、id：版本与示例身份；source：图像身份、哈希、原尺寸、视口、图框和路径。
- calibration：frequencyDirection、frequency/amplitude 两点标定、单位、幅值依据说明。
- curves：稳定曲线 ID、名称、颜色、稳定点 ID 与原图 x/y、连续片段 ID、修改状态。
- zero：用户点选的零频源像素与显式补选的点 ID；不等于科学批准。
- operations：添加、删除、移动、标定、零频、恢复等操作摘要。
- 初始 fixtures 不可变；工作文档、副本历史、已保存文档分离。视图缩放/选中不纳入数据历史。

## 校验

来源 ID/哈希/尺寸与当前示例一致；文档版本正确；标定两点不同且数值有限；点 ID 唯一、在图框内、各曲线频率严格有序；字段/曲线身份与示例匹配。损坏草稿不自动覆盖。

## 人工连线标记

Point.manual（可选布尔）区分补选点，Point.breakBefore（可选布尔）保留删除断边；缺省保持旧格式可读。恢复旧草稿时按初始点 ID 集补充 manual，数值和原存储不变；显式保存才持久化。
