# 数据模型

## 正式存储

正式路径使用现有SpectrumCollection/SpectrumRun，无新增表。新运行 result_json 包含数值曲线、逐曲线 manual_documents、服务端 manual_provenance（作者/父运行/时间）和 manual_zero_checks。集合版本增加并切换当前run，review_json清空，旧run保留。返修复制后编辑身份重新绑定新集合，来源及像素保留。

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

## 描线与数值排序分离

Curve.pathOrdered（可选布尔）为真时 points 数组表达描线顺序；每点 breakBefore 是该顺序中前一条边的断开标记。旧曲线未带字段时按历史频率序列读取并冻结连线，不移动点。数值表通过 ordered 单独排序；科学积分未接入，不能把重复/回退频率草稿当作已采纳谱。

## 坐标轴参照与点读数

已识别轴记录为独立只读 reference（源图ID/哈希、频率像素刻度、单位、λ参考像素刻度、来源文件哈希）。用户文档仍只持久化当前 calibration/zero/points，不迁移或覆盖旧草稿。新增点选中状态和辅助层开关为视图状态。

## 保存后零频检查结果

检查结果是保存快照的派生视图：边界状态、各曲线完成/待确认/缺失、最近点ID与频率/像素距离。zero.pixel/pointIds 仍是显式操作证据；不增加持久化“已通过”标记。删点或改标定后的结果按当前保存快照重新计算。

## 正式末端吸附边

Point.joinTo可选字符串指向同曲线另一已有点，表达尾点附加连接；允许引用任意顺序目标，但禁止自连/悬空/重复边。既有connectTo父点约束不变。保存数值点、CSV join_to与编辑文档保持；删除/公开裁剪移除丢失目标引用。旧格式无此字段继续兼容，无表结构变更。Demo数据契约不变。

## 重算结果
复用不可变SpectrumRun，无DDL。quality.recalculations按kind存来源和时间；parameters独立保存λ/ωlog状态；dos_mode_integral分开表示积分及3N比较。点、连线、manual_documents及来源保持不变；编辑保存清除重算派生值。

## 拓扑诊断与定位
quality.trace_diagnostics为重算派生JSON，无DDL；点坐标及ID由保存谱生成，不改变点或连接。编辑器initialPointId只作选中，focusPointId作一次性视图定位，不写数据库或撤销历史。

## 材料确认版本
复用SpectrumRun，无DDL。state_revalidation记录base_run_id、previous_state_signature、state_signature、author_id、confirmed_at及material_summary；旧run保留。数值点/标定/编辑文档原样复制，派生积分与采纳清空。

## 高频末端证据及自动修订
Document.highEndpoint存人工确认快照，默认为空；不是科学采纳。quality.automatic_repairs为本次可追溯连接报告，全部点及其ID保留；重算创建新run。后台已有时间/参考信息保留，前端03不展示。

## 高频确认字段已废弃
highEndpoint只作为旧run历史记录保留。GET编辑文档移除该字段，POST编辑保存忽略旧客户端字段；当前计算完全不依赖它。高频上限来自保存点，DOS分别记录各分波区间。

## 直边插点与断口补接
不新增字段。直边插点把本次新点放在原边较后端点前，按ID局部重接前驱，删除被替换直连；其他原点的相对顺序、ID、坐标、其他边保留。未连片段继续新增链和joinTo终点，不删除原边。两类操作都由保存调整写新run，旧run保持。
