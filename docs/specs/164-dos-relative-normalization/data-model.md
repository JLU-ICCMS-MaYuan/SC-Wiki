# 数据模型

沿用 SpectrumRun.result_json；不新增表。

quality.dos_relative：method=dos-relative-v5，spectrum_type（total 或 projected）、components（curve_id、projection、status、area、unit、frequency_interval_thz、amplitude_basis）、shares（status、reason、total_area、fractions、expected_fractions、composition_source）、normalization（status、reason、coefficient、primitive_atoms、target_modes、component_mode_integrals、expected_modes、deviations、structure_evidence）。
quality.dos_mode_integral：保留原始绝对积分接口，不混入像素或 3N 推导值。
candidates.dos_relative_normalized：仅归一化成功时提供；按曲线身份保存各自频率和密度，附共同系数/来源/模式单位；不是科学采纳。
frequency_range_confirmed 已退休：新模型不生成；旧输入在模型校验前忽略该字段，其他未知字段仍拒绝。旧数据库记录保留，不再参与计算。

新重算创建新运行，保留旧版本。重复重算替换候选不累乘系数；人工保存清空派生数据。隐藏/限定曲线不能通过总量、比例、系数、候选泄露。

shares.element_ratio 保存 elements、reference_element、estimated_ratio、expected_ratio、reference_label、formula、share_difference_pp、max_share_difference_pp 及 status/reason；shares.coverage_note 不再生成或展示。公开过滤沿用 shares 整体失效规则。

## TDOS结果语义

当前 quality.dos_relative.method=dos-relative-v5，新增 spectrum_type=total|projected。total 仅表示明确总谱身份，不自动确认科学正确；physical_definition_confirmed 仍是归一化前提。components 保留总谱 curve_id、projection、面积和实际范围。TDOS 的 shares.status=unavailable，reason 说明未提供元素分波，不生成 fractions、expected_fractions、element_ratio；normalization 可独立 available。TDOS component_mode_integrals 保留总谱积分，expected_modes/deviations 为空，不伪造逐元素积分；可靠材料组成可通过独立composition字段展示原子数占比。候选 method 同为 v5，原始点、旧记录与科学表单标准键不变。

## 纵轴刻度优先的结果语义（已实施）

继续用 components.area、unit、frequency_interval_thz 和 amplitude_basis 表达独立积分。area含义随明确记录的幅值依据：有可信标定时为纵轴数值积分，unit为原纵轴单位乘THz；无可用刻度时才为像素面积，unit为pixel·THz。不能只把旧像素结果改成任意单位标签。人工标定存在时依据当前人工值，原始描线和原始标定仍保留。

normalization.coefficient对应本次选用的幅值单位，候选密度由该幅值乘系数生成。任意单位面积不填入dos_mode_integral冒充绝对模式数；原始绝对积分及逐曲线稳定身份沿用。v5的amplitude_basis.kind=calibrated_values时，附unit、slope、intercept、baseline_pixel、direction以及source（manual_calibration或source_calibration）；像素依据沿用source_pixels/stored_pixels并附unit=pixel。原始输入不改写，未改动标准科学表单键。

## 独立组成信息

quality.dos_relative新增可选composition={fractions:元素到原子数比例,source:计量依据}，复用既有化学式优先、结构计数后备的来源规则。该字段不依赖shares或normalization状态，不包含曲线ID。components仍仅保存真实已提取曲线；表格缺失分波的元素行由前端据组成补齐，不保存伪曲线、不参与积分或候选生成。旧v5无composition时只复用已有可信structure_evidence.species_counts，不修改旧数据。
