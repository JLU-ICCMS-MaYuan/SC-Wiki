# 正式接口契约

沿用GET/POST manual和POST recalculate及现有权限/版本字段，无新API或表。
manual.calibration.amplitudeEvidence允许省略/空，不要求用户说明；不再因其缺失拒绝物理幅值标定修改。
重算α²F使用当前源像素，返回独立omega_log参数及normalization；缺少参考/数学无定义作为各结果状态返回，不阻止编辑保存。
归一化源自当前材料同条件唯一λ，不接收浏览器伪造积分/C。新候选附曲线及基础run引用；旧源曲线不覆盖。
DOS仅共享移除说明输入/必填规则，积分与3N不变。公开未采纳/受限频段不返回完整归一化候选。
