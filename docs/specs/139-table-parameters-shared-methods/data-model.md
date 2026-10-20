# 数据模型：科学参数、阶段和来源关联

字段失效与重核版本由[后台修复增量](association-recheck.md)补充：带 `field_binding` 的新关联按字段依赖比较，旧格式仍保守读取；通过当前原文核对的新关联保存在核对结果的 `association_review`，原 payload 关联保留为历史。下文整条 `target_fingerprint` 继续用于旧格式及补空前的并发检查，不再作为新字段绑定的唯一失效条件。

**依据**：[Spec](spec.md)、[设计决策 D3～D5](research.md)。契约已按本轮实现落地，运行边界见 validation.md。

## 数据所有权

- 科学值的唯一业务副本仍是材料状态下的 `property_modules[].records[]`，提交后保存到现有 `PropertyRecord.payload_json`。
- 引句与定位复用记录 `evidences` 及现有证据持久化关系；来源关联元数据随 payload 保存，不依赖 Redis 或运行目录恢复业务值。
- 临时上下文清单、模型响应和未采纳候选保存为上传运行制品，仅用于复现及审计，不作为第二套 Issue 状态或科学主数据。

## 结果参数与身份

| 字段 | 表达与约束 |
| --- | --- |
| 材料状态 | 化学式、物相、压力沿用现有状态；未知值保留未知 |
| `record_type` / `property_code` | 预测结果为 `predicted_tc` / `tc` |
| `method_code` | 沿用方法枚举，如 `isotropic_eliashberg`；无来源不猜测 |
| `value_number` 或 `value_min/value_max` | Tc 规范值，单位 K，原文限定保留在 `value_raw` |
| `payload.parameters.lambda_ep` | 非负有限数，无量纲；兼容旧包装对象仅在边界读取 |
| `payload.parameters.omega_log` | 非负有限数，K；`omega_log_k` 只在输入边界归一化 |
| `payload.parameters.mu_star` | 明确共用的单个 μ*；与同名范围互斥 |
| `payload.parameters.extensions` | 沿用已有扩展列表，保存 μ* 范围或未配对报告范围 |
| 近似与表行 | 在来源关联元数据及阶段扩展保存 harmonic／anharmonic 和原始表行身份；去重必须包含它们，不能只按压力或 Tc 合并 |

不把 λ、ωlog 或 μ* 放在材料状态级再传播；它们属于具体结果与计算条件。

## μ* 的两种范围

- 明确 `Tc_min↔μ_max`、`Tc_max↔μ_min`：沿用扩展 `key=mu_star`、`value_kind=range`、`value_min=0.1`、`value_max=0.16`、`unit_raw=1`；Tc 是 281–311 K。保留原注 `0.16 to 0.1` 及明确配对依据。
- 只报告 μ* 范围、未给配对：扩展键为 `mu_star_reported_range`，上下界递增并保留原文；不创建特殊 `mu_star` 范围，不填两端 μ*。关联说明标为待核对。
- 其他显式对应若不能用现有范围表达，保留为两条已配对的标量记录，共享原始表行身份。没有配对证据不拆出猜测结果。

## 计算阶段

`calculation_conditions.calculation_code/electronic_method/exchange_correlation_functional/k_grid/q_grid/k_broadening/q_broadening` 继续使用现有字段。平面参数只属于记录的主声子／EPC 阶段；没有单一可判定主阶段时不混填。

其他阶段与补充数值使用既有 `extensions[]`：`key` 加阶段前缀、`name` 标明阶段、`value_kind`、`value_raw`、数值或范围以及 `unit_raw`。例如 `sscha.k_grid` 为 `3×3×3` 文本、`sscha.energy_cutoff` 为 80 Ry。原胞与超胞网格、SSCHA 的 2×2×2 采样与插值后 6×6×6 网格分别保留。展宽及未知单位留空，不从图中或软件默认值推测。

## 新增附加元数据：payload.source_associations

新增 JSON 列表，每个条目绑定一个最终目标字段；旧读者可忽略，但不能在往返时删除。不存在该字段的历史记录保持原行为。

| 字段 | 约束 |
| --- | --- |
| `version` | 当前内部元数据版本 1，不改变科学草稿顶层版本或已发布表单定义 |
| `target_path` | 相对当前记录的 JSON Pointer，只允许 parameters、calculation_conditions、方法相关指定路径；禁止改身份、权限与 Tc 结果数值 |
| `basis_kind` | `paper_quote` 或 `paper_inference`；本功能不生成 `general_knowledge` |
| `stage` | 计算阶段，例如 `electron_phonon`、`sscha`；未知不得硬填 |
| `scope` | 原文支持的材料、相、压力范围、近似、方法与例外；字段缺省是未知，不表示适用全部 |
| `reported_value_raw` / `unit_raw` | 原始报告文本、原单位；转换需记录规范单位与转换规则 |
| `fact_evidences` | 参数值的 file/page/block/逐字引句引用 |
| `scope_evidences` | 适用关系、表注／表头或 Methods 的原文引用；可与值引文不同 |
| `explanation` | 简短依据、关联、局限；推断必填，不保存内部逐字思维 |
| `table_row_ref` | 可选的 file_id、table_id、row_index、分组；无可靠结构时保存原始块组和局限，不伪造表 ID |
| `target_state_fingerprint` | 服务端绑定材料、物相和压力；同一标准空间群符号自动补出一致群号视为等价，冲突群号或压力改变仍失效 |
| `source_documents` | 服务端记录全部有效 main／SI 的文件 SHA-256 与角色，提交时转换文件 ID；原引句仍存在但文件内容或角色改变也失效 |
| `source_fingerprint` / `target_fingerprint` | 服务端由有效来源及当前目标内容计算，变化后旧关联失效；不信任客户端自报的审核状态 |

目标科学指纹使用当前记录的科学字段及参数／条件，排除 `source_associations`、自身指纹、运行时间等元数据，避免循环 hash。应用前比较候选的预期当前指纹，合并成功后将说明重新绑定到最终科学值指纹；既有 record_key 不因补参数而更换，record_checksum 按原规则重算。

条目唯一性由当前记录、目标路径、来源及规则版本决定；同路径冲突候选保留为待审，不生成两个互相覆盖的已采纳值。证据对象须能通过现有定位规则，文本来源没有 PDF 几何时不伪造页码或块。

## 内部上下文与关联候选

上下文包包含来源文件角色、版本／hash、全部读取窗口及状态、表格包、Methods 设置、局部例外和未读区域。关系候选指向已有记录及允许的字段，携带前述值／范围证据；原始响应不直接作为业务数据。

服务端用当前任务来源白名单、目标身份、阶段和字段冲突做机械校验；语义仍由核对与人工审查。不能声称这些机械校验已证明物理正确性。

## 生命周期与失效

1. 直接事实提取、归一化，经过已有 Claim 定位与覆盖检查。
2. 模型提出共用关系。证据不完整、冲突或来源未读时留候选并说明原因。
3. 有依据的推断在既有建议阶段补空，附来源关联，并维持 `uncertain`／推断标签；不是 `paper_quote` 的 `validated` Claim。
4. 保存时同时保留 payload、证据及既有核对结果的内容／来源绑定。正式提交和审核沿用原门槛。
5. 人工更改值、范围、方法或来源后，服务端重新计算指纹；旧解释不能继续作为新值的证据。重试不重复增加扩展和来源条目。
6. 定向重跑仅合并仍为空且目标版本一致的字段，已有人工值或更具体条件不被覆盖。未采纳候选和旧尝试保留。

## 持久化与兼容性验证

复用现有 JSON 和证据关联，不新增数据库表或数据迁移；需使用隔离 MySQL 验证草稿、正式提交、返修、重开及导出。浏览器无需读取任务运行制品。旧参数包装对象、旧 ωlog 名称和旧范围在既有边界转换，正常请求不依赖旧表查询。
