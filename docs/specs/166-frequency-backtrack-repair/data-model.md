# 数据与生命周期

quality.frequency_repairs[kind]：逐曲线报告，包含curve_id/name、当前仍有效的修正点列表、最大原图位移、本次新增修正点数/块数、未处理块及原因。
Document.operations中新kind=auto-frequency-repair，detail为JSON：batch_id、direction、frequency_calibration、changes（[point_id,before_pixel,after_pixel]数组）；同批可分片，每片不超过4000字符。
撤销kind=undo-frequency-repair，detail记录batch_id；随后manual保存仍创建新版本并清空旧积分。

曲线frequency_pixel与frequency_thz、编辑点对应x/y同步变更；状态明确为自动频率微调，幅值及连接保持。当前坐标与记录不符时不把历史修正当作当前有效修正，不直接撤销覆盖它。
报告不是科学采纳或正确性证明。原图文件、旧run、其他曲线保持；不新增数据库字段。
