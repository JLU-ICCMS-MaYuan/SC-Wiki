# 数据模型

沿用 SpectrumRun.result_json；不新增表。

quality.dos_relative：method=dos-relative-v1，components（curve_id、projection、status、area、unit、frequency_interval_thz、amplitude_basis）、shares（status、reason、total_area、fractions、expected_fractions、composition_source）、normalization（status、reason、coefficient、primitive_atoms、target_modes、component_mode_integrals、expected_modes、deviations、structure_evidence）。
quality.dos_mode_integral：保留原始绝对积分接口，不混入像素或 3N 推导值。
candidates.dos_relative_normalized：仅归一化成功时提供；按曲线身份保存各自频率和密度，附共同系数/来源/模式单位；不是科学采纳。
calibration.curves[].frequency_range_confirmed：可选布尔，默认 false；仅表示原图频段完整性证据，仍核对采样覆盖标定频段和裁峰。

新重算创建新运行，保留旧版本。重复重算替换候选不累乘系数；人工保存清空派生数据。隐藏/限定曲线不能通过总量、比例、系数、候选泄露。
