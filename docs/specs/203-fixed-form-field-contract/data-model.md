# 数据与所有权

论文通用21项：title、knowledge_graph_title、authors、corresponding_authors、co_first_authors、journal、year、volume、issue_number、pages、doi、paper_type、theoretical_subtype、superconductor_kind、material_families、abstract、keywords_tags、methodology、summary、key_finding、research_motivation。

材料状态通用11项：material_name、material、element_count、material_dimensionality、crystal_system、reported_space_group_symbol、reported_space_group_number、structure_families、state_kind、pressure_value_gpa、structure。结构优化沿structure_optimization保存。

计算条件公共字段：calculation_code、electronic_method、exchange_correlation_functional、phonon_method、vibrational_treatment；软件组qe、epw、sscha。组内白名单由共享契约提供，保留原始值、类型及unit_raw。人工extensions与标准值分开，不信任模型自报human来源。

Tc参数沿parameters.lambda_ep/omega_log/mu_star及既定范围表达；共同资料仍为metadata.tc_contexts/tc_context_ref。谱使用独立集合及curve.kind，不复制进payload。热力学为thermodynamic_stability.basis/cases及既有7项case字段。

S.structure承接structure_format/structure_text、空间群、来源、校验、派生表示、派生依据及人工备注。解析临时候选不成为第二个正式结构容器。契约版本和业务身份由服务端负责。

ScientificWorkDraft/原科学实体图持有当前值；Redis为缓存；PaperHistoryEvent冻结快照只读。迁移后旧核对绑定不得当作新内容自动通过。

## 论文通用字段明细

|固定路径|类型|
|---|---|
|paper.title|text|
|paper.knowledge_graph_title|text|
|paper.authors|text[]|
|paper.corresponding_authors|text[]|
|paper.co_first_authors|text[]|
|paper.journal|text|
|paper.year|integer|
|paper.volume|text|
|paper.issue_number|text|
|paper.pages|text|
|paper.doi|text|
|paper.paper_type|enum|
|paper.theoretical_subtype|enum|
|paper.superconductor_kind|enum|
|paper.material_families|selection[]|
|paper.abstract|text|
|paper.keywords_tags|text[]|
|paper.methodology|text[]|
|paper.summary|text|
|paper.key_finding|text|
|paper.research_motivation|text|

## 材料状态通用字段明细

|固定路径|类型|
|---|---|
|S.material_name|text|
|S.material|text|
|S.element_count|integer|
|S.material_dimensionality|enum|
|S.crystal_system|enum|
|S.reported_space_group_symbol|text|
|S.reported_space_group_number|integer|
|S.structure_families|selection[]|
|S.state_kind|enum|
|S.pressure_value_gpa|number:GPa|
|S.structure|structure|

## 材料状态科学分类字段明细

|固定路径|类型|
|---|---|
|S.structure_optimization|enum|

## 计算条件明细

C 表示 R.payload.calculation_conditions；每个软件组独立保存，不跨组补值。

|固定路径|含义|
|---|---|
|C.calculation_code|计算软件|
|C.electronic_method|电子结构计算方法|
|C.exchange_correlation_functional|交换关联泛函|
|C.phonon_method|声子方法|
|C.vibrational_treatment|振动处理层次|
|C.qe.k_grid|k 网格|
|C.qe.q_grid|q 网格|
|C.qe.q_grid_interpolated|插值 q 网格|
|C.qe.k_broadening|k 展宽|
|C.qe.energy_cutoff|波函数／平面波截断能|
|C.qe.charge_density_cutoff|电荷密度截断能|
|C.qe.supercell|超胞|
|C.qe.atoms|原子数|
|C.qe.temperature_k|计算温度|
|C.qe.convergence_energy|能量收敛阈值|
|C.qe.convergence_force|力收敛阈值|
|C.epw.k_grid|k 网格|
|C.epw.q_grid|q 网格|
|C.epw.q_grid_interpolated|插值 q 网格|
|C.epw.k_broadening|k 展宽|
|C.epw.q_broadening|q 展宽|
|C.epw.temperature_k|计算温度|
|C.epw.matsubara_frequency_cutoff|Matsubara 频率截断|
|C.sscha.k_grid|k 网格|
|C.sscha.q_grid|q 网格|
|C.sscha.q_grid_interpolated|插值 q 网格|
|C.sscha.k_broadening|k 展宽|
|C.sscha.energy_cutoff|波函数／平面波截断能|
|C.sscha.charge_density_cutoff|电荷密度截断能|
|C.sscha.supercell|超胞|
|C.sscha.atoms|原子数|
|C.sscha.temperature_k|计算温度|

## 本次变更登记

- #203：移除四个压力辅助键、method_scope、声子阶段扩展路径及新表单band_gap项目；保留直接phonon_method与历史band_gap。计算参数移到已审定软件组，类型与原单位保持。
- #204：规范结构S.structure承接旧根容器有意义内容、来源、验证及派生表示；旧根容器退出新正式契约。
- 今后修改任何标准键、类型或含义，须创建并审查对应Issue/Spec变更登记，再显式升级清单和锁定摘要；不得用更新测试快照替代审查。人工扩展通过现有人工入口创建，与标准字段分开。
