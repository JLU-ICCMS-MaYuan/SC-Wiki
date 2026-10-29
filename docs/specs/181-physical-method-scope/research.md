# 技术调查与取舍

## 已确认故障

state_optimization.resolve_candidates 在确认结构优化后，把模型返回的 approximation 写到状态下所有 property_modules 记录。结构工作流不能证明所有电子或振动结果使用同一近似；此处删除广播，不用下游核对代替源头修复。

## 复用与所有权

- 继续以 PropertyRecord.payload_json 的 calculation_conditions 表达具体结果的计算条件。electronic_method 是电子理论，phonon_method 是响应/声子技术，vibrational_treatment 是振动层次；其他阶段仍复用 stage.parameter 扩展和 source_associations，不建第二套工作流状态系统。
- 新字段 method_scope 保存物理对象、阶段、工作流身份及明确的修正关系。普通电子带隙/DOS 不接收无关声子条件；明确电子—声子修正关系与原句依据时允许关联，不把电子性质全部封死。
- 结构优化目标使用 unknown/classical_static/quasi_harmonic/anharmonic_quantum。sscha 只作为旧值兼容，不重写既有数据。具体方法、软件、电子理论、温压和三项几何自由度保存在状态的 structure_optimization_details JSON；不与结果自身条件混用。
- 新条件沿现有提取、建议、保存、核对和导出路径验证；结构优化模型只更新结构目标、对应详情与来源，不更新任何物性近似。

## 历史与迁移边界

payload.approximation 不整列改名；旧值原样保存并明确标成历史混装字段，按当前记录的真实语义核对。新提取提示改用明确字段，错类进入已有有界纠错及原始响应留档，不按字符串把历史 DFT/harmonic 变成新的科学事实。
数据库只新增可空 JSON 列并放宽目标枚举约束；不回填、不改科学值、不将旧 sscha 升级为量子非谐几何已证实。迁移文件随代码交付，仅在隔离数据库验证，未授权不应用业务数据库。

## 科学约束

沿用已确认 Spec 的科学参考，不把 0 K 当静态晶格，不由 SSCHA 名称推定变胞，不因几何未变化否认实际优化。HF/DFT+U 和其他报告理论不采用封闭白名单；振动层与求力技术不能互代。未报告的泛函/U不补猜。

## 验证方法

先固定旧响应重放并证明广播故障；再用正文/SI原PDF哈希和IR身份核对的文字重提 CaH2 带隙、CaH4 DOS及邻近Tc/方法字段，经过正式归一化、结构关联、组装与保存重读。原任务只读，真实调用失败就保留未完成项，不用旧答案代替。

## 兼容与依赖收敛

现有source_associations生产者使用v2字段绑定，原验证器仅接受v1会使合法补空记录无法保存；本次沿用已落地的v2结构及64位指纹校验，保留v1兼容，拒绝未知版本。未改绑定数据所有权或审批权限。振动层次用完整词匹配，避免harmonic子串错误授信；旧正确字段不因全局规则版本重置而失效。只在真实依赖或作用域变化时重新核对。
