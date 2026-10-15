# demo 谱数据契约

> 历史 demo 合同；正式数据库与接口见 [contracts/production.md](contracts/production.md)。模型只能提出标定，数值和质量由服务器共享算法生成。

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

## 精度核验增量

provenance.algorithm_version=precision_audit_v3；原 curves、points、diagnostics 和 DOS 候选保持 v2 原值。

- precision.zero_baseline_candidate：原图零参考带、可见像素区间、不可分辨幅值区间、候选序列及每点理由、独立积分和事后对照。accepted=false；保留候选零值所依赖的假设。
- precision.cumulative_moment：累计曲线的单调候选、负增量数、最大调整量、可读频率范围、Δλ、对数矩和未覆盖低频区间。diagnostic_only，不替换原累计曲线。
- precision.projection_mode_check：元素模式数条件目标、实际面积与偏差，明确完整正交投影和共尺度假设。
- precision.automatic_checks：来源哈希、连续性、零参考带有效性及累计核验可计算性；不表达科学采纳完成。
- scientific_acceptance=requires_user_review；training_ready 仍为 false。
- CSV 新增 zero_baseline_candidate_amplitude 与 zero_baseline_candidate_reason，只在 α²F 行填写；其单位沿用该曲线原图坐标单位。

## 科学复核增量

algorithm_version=scientific_audit_v4 修复零频首区间积分，增加 integration_method、zero_interval_lambda；原始曲线点与 DOS 候选保持不变。

可选顶层 scientific_review 保存复核身份、范围、用途分级、原文异常、分频段核验、灵敏度及 dataset_fingerprint。状态 completed_with_restrictions 表示已执行 AI 科学复核，不表示全部数据采纳；quantitative_ml_approved=false。原曲线 needs_review 表示未作为正式科学值批准，原 precision 的 requires_user_review 仍是生成时默认状态，显式复核以顶层已绑定记录为准。

指纹覆盖来源、标定、算法版本及材料状态数值，排除生成时间和复核自身。重建数据变化必须重新复核。CSV 补充 scientific_review_status/quantitative_ml_approved，与 JSON 和页面结论一致；不改变 training_ready=false。

## 图像约束增量

algorithm_version=image_constraints_v5。原始 4654 点及 DOS 数值保持不变。precision.joint_reconstruction 独立保存 α²F 与累计 λ 候选序列、绿色像素上下界、零轴偏移、裁边频率掩膜、全点/留出误差及积分；uses_paper_reference=false。每五个真实粉点留出一个，未将虚线插值当观测；consistency_is_constraint_not_independent_accuracy=true。边框掩膜覆盖约 28.6–29.0 THz。

科学复核新增 conditional_quantitative_use=true 与 supersedes，quantitative_ml_approved=false 表示没有把全曲线无条件批准为作者真值。metrics.states[].bins 保存累计谱原图范围、原/联合候选相容状态，旧点估计差仍保留但明确不代表测量误差；共同域只覆盖真实观测。evidence 保存派生标注 SVG 路径、哈希与来源。

CSV 新增 joint_candidate_amplitude、joint_candidate_cumulative_lambda、joint_boundary_mask（仅 α²F 网格行填写）及 conditional_quantitative_use。原点来源与曲线状态不覆盖。
