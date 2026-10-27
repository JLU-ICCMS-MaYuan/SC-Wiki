# 数据模型

沿用 SpectrumRun.result_json；不新增表。

quality.dos_relative：method=dos-relative-v2，components（curve_id、projection、status、area、unit、frequency_interval_thz、amplitude_basis）、shares（status、reason、total_area、fractions、expected_fractions、composition_source）、normalization（status、reason、coefficient、primitive_atoms、target_modes、component_mode_integrals、expected_modes、deviations、structure_evidence）。
quality.dos_mode_integral：保留原始绝对积分接口，不混入像素或 3N 推导值。
candidates.dos_relative_normalized：仅归一化成功时提供；按曲线身份保存各自频率和密度，附共同系数/来源/模式单位；不是科学采纳。
frequency_range_confirmed 已退休：新模型不生成；旧输入在模型校验前忽略该字段，其他未知字段仍拒绝。旧数据库记录保留，不再参与计算。

新重算创建新运行，保留旧版本。重复重算替换候选不累乘系数；人工保存清空派生数据。隐藏/限定曲线不能通过总量、比例、系数、候选泄露。

shares.element_ratio 保存 elements、reference_element、estimated_ratio、expected_ratio、reference_label、formula、share_difference_pp、max_share_difference_pp 及 status/reason；shares.coverage_note 不再生成或展示。公开过滤沿用 shares 整体失效规则。
