# 数据模型

源curves保留像素、标定、ID和连线；manual_documents保留源编辑，不写归一化幅值。
quality.integrals.raw：method、pixel_integral及状态、omega_log_k及parameters.omega_log、实际频段、normalization。
normalization：status、lambda_reference、pixel_integral、coefficient、lambda_normalized、source、reason、method=paper_lambda。
quality.comparisons.raw.omega_log：value/reference/absolute_difference/relative_difference_pct及来源，零参考相对偏差为空。无lambda独立对比。
candidates.alpha2f_lambda_normalized：curve_id、frequency_thz、relative_amplitude、alpha2f、unit、像素基线/方向、参考来源、基础run。结果归属不可变新run。
说明字段amplitudeEvidence可缺/空，缺省沿用旧值或空串，仅作兼容历史信息，不参与数学可用性判定。
