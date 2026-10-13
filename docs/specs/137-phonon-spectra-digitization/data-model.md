# demo 谱数据契约

schema_version=1，仅为 demo 合同，不改变现有 PropertyRecord 标量合同。

- source：PDF/补充文件名与 SHA-256、页码、图号、原图 SHA-256、尺寸、PDF 区域及标定方式。
- material_states：formula、phase、pressure_gpa、structure_evidence、primitive_atoms、mode_count；每状态含独立 curves。
- curve：id、kind、projection、raw_unit、axis_calibration、data_points、review_status、training_ready=false。
- data_point：frequency_thz、pixel_x/y、observed_amplitude、reconstructed_amplitude、pixel_low/high、status。缺失用 null，不写 NaN、不以 0 代替未知。
- status：observed、interpolated、baseline_inferred、boundary_assumption、missing。归一化预览单独保存，不能覆盖 observed_amplitude。
- dos_normalization_candidate：共同因子、目标模式数、积分结果、元素面积、假设与确认状态。只有完整曲线才计算候选；未确认共尺度时 accepted=false。
- diagnostics：λ/ωlog 积分、正文参考、相对偏差、缺口、裁边与低频敏感性。包络与敏感性不是统计置信区间。
- reference：正文 λ、ωlog 及原文位置；只参与事后比较，不参与提取或拟合。

原始位图、配置摘要、软件版本和运行报告一同输出。CSV 每点携带状态身份、来源摘要及点状态，不能只导出两列失去上下文。demo 不提供自动批准或业务入库操作。
