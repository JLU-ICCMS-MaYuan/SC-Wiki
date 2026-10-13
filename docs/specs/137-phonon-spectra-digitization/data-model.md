# demo 谱数据契约

schema_version=1，仅为 demo 合同，不改变现有 PropertyRecord 标量合同。

- source：PDF/补充文件名与 SHA-256、页码、图号、原图 SHA-256、尺寸、PDF 区域及标定方式。
- material_states：formula、phase、pressure_gpa、structure_evidence、primitive_atoms、mode_count；每状态含独立 curves。
- curve：id、kind、projection、raw_unit、axis_calibration、data_points、review_status、training_ready=false。
- data_point：frequency_thz、frequency_pixel、amplitude_pixel、observed_amplitude、reconstructed_amplitude、pixel_low/high、status、detection_mode。结合 frequency_direction 将频率与幅值像素转换为原图 x/y。缺失用 null，不写 NaN、不以 0 代替未知。
- status：observed、interpolated、baseline_inferred、boundary_assumption、edge_continuation、missing。归一化预览单独保存，不能覆盖 observed_amplitude。
- detection_mode：strict_color / chromatic_recovery，仅直接观测填写；其余为 null。curve.chromatic_recovered_points 单独统计真实暗色补读点，provenance.algorithm_version 标明 chromatic_recovery_v2。CSV 同样保留此字段。
- dos_normalization_candidate：共同因子、目标模式数、积分结果、元素面积、假设与确认状态。只有完整曲线才计算候选；未确认共尺度时 accepted=false。
- diagnostics：λ/ωlog 积分、正文参考、相对偏差、缺口、裁边与低频敏感性。包络与敏感性不是统计置信区间。
- reference：正文 λ、ωlog 及原文位置；只参与事后比较，不参与提取或拟合。

原始位图、配置摘要、软件版本和运行报告一同输出。CSV 每点携带状态身份、来源摘要及点状态，不能只导出两列失去上下文。demo 不提供自动批准或业务入库操作。
