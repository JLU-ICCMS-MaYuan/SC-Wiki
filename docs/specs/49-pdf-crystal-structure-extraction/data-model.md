# 数据模型：论文附件晶体结构提取

**GitHub Issue**：[#49](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/49)

## 设计原则

2026-10-20 增补：下文既有结构候选与状态规范几何契约继续保留。另设 `paper_structural_records`，使论文报告的结构和部分几何信息在不关联材料状态、没有 Tc 的情况下独立保存。规范几何的 `confirmation` 与资料的 `retention` 分开，不通过伪造 Tc 或主要研究状态取得可检索性。

### 论文独立资料 `paper_structural_records`

| 字段 | 含义与约束 |
| --- | --- |
| `id`、`record_key` | 服务端资料 ID、稳定来源标识；同一论文 revision 内来源键唯一 |
| `paper_id`、`paper_revision` | 唯一来源论文及内容版本；旧版本资料保留，读取只取当前版本 |
| `kind` | `model` 完整结构；`lattice` 部分几何；`issue` 仅供内部核对的提取问题 |
| `material`、`elements`、`system_key` | 从实际几何／报告化学式校验出的材料与自身元素集合，供无 Tc 查询 |
| `pressure_gpa`、`space_group` | 明确报告的压力与空间群；未知保持空 |
| `state_key` | 可选关联状态；不构成保存前提，也不作为独立资料的删除外键 |
| `retention` | `pending` 待核对；`retained` 明确保留；`excluded` 明确不保留；提取问题始终 pending |
| `data_json` | 完整原始／派生坐标、表示、参数、单位、原文分组、逐行来源及保留决定 |

来源只保存文件身份、原名、角色、哈希、页码、表／行、几何位置和引句，不对客户端输出服务器路径。完整几何在服务端重新读取、核对化学计量并生成派生表示，不信任浏览器提供的哈希、元素与“校验通过”。几何资料与原附件不因材料状态删除而丢失。

### 草稿增补

`structure_candidates[]` 增加 `retention`；`retained` 允许 `material_state_ref="unassigned:*"`，不改变既有 `confirmation=confirmed` 必须关联状态的规范几何门。

`structural_observations[]` 保存来源键、化学式、原空间群、压力、原文近似分组、直接报告的 `cell_parameters`、对称性派生参数、单位、键长范围、`coordinate_status=not_reported` 和 `retention`。同一压力的谐／非谐行不共用来源键。

`structural_extraction_issues[]` 保存无法恢复的布局、单位或分组原因；`structural_extraction_version` 表明解析版本。问题资料可以随论文保留，但从不进入公开结构搜索，也不能导出为完整原子文件。

### 保存、返修与公开

资料写入由 `persist_scientific_draft` 的同一事务调用，失败回滚不留下半套来源资料。返修读取恢复独立模型、观测和保留决定；升版创建新 revision 资料并保留旧版本。管理员通过旧请求体修改其他字段时，服务端仍继承未加载的独立资料。

公开查询要求 `retention=retained`、来源论文 `review_status=approved` 且已批准 revision 与当前内容及资料版本一致。上传者／有权限的管理员可查看当前私有资料。模型为原胞／惯用胞提供 CIF、POSCAR；部分观测只提供带来源 JSON／CSV，不制造原子位置。

结构候选是上传草稿阶段的临时聚合；正式结构沿用 #32 的 `StructureModel`，不新增结构级审核
状态。原始输入、直接报告字段和派生表示分别保存，避免把推导内容误标为论文原文。

## 草稿实体

### `structure_candidates[]`

| 字段 | 类型 | 必填 | 约束 |
|---|---|---:|---|
| `candidate_id` | string | 是 | 当前上传任务内稳定唯一 |
| `material_state_ref` | string | 是 | 指向 `material_states[]` 项 |
| `source_kind` | enum | 是 | `attachment`, `pdf_reported`, `pdf_derived`, `merged` |
| `status` | enum | 是 | `needs_review`, `valid`, `confirmed`, `excluded`, `blocked` |
| `confirmation` | enum | 是 | `unreviewed`, `confirmed`, `excluded` |
| `original_format` | enum/null | 否 | `cif`, `poscar`；PDF 候选为空 |
| `original_text` | string/null | 否 | 原始结构文本，不可被派生输出覆盖 |
| `reported_structure` | object | 否 | 原文直接报告的晶格、坐标、空间群和占位 |
| `derivation` | object/null | 否 | 展开或标准化方法、输入位点、推导摘要 |
| `validation` | object | 是 | ASE 解析状态、错误、元素、原子数、晶胞、体积和哈希 |
| `representations` | object | 否 | `primitive`、`conventional` 两个派生结构引用 |
| `sources[]` | object | 是 | 文件、角色、页码、章节/表格、quote、evidence_ref |
| `conflicts[]` | object | 是 | 条件或几何冲突说明 |
| `user_note` | string/null | 否 | 用户修正说明，不替代原文证据 |

### `structure_candidates[].representations`

每个表示包含 `cell_kind`（`primitive` 或 `conventional`）、`format`（`cif` 或 `poscar`）、
`text`、`derived_from_candidate_id`、`standardization_method` 和 `validation`。表示是可重新
生成的派生内容，不能作为新的独立论文来源。

## 正式实体

正式提交使用 #32 的：

- `material_states`：保存材料、压力和论文报告空间群；没有完整几何时仍可存在；`phase_label` 已废弃。
- `structure_models`：保存完整 `structure_format`、`structure_text`、哈希、生成方法、核处理和
  可选父结构；必须绑定同一 `paper_id + paper_revision + material_state_id`。
- `paper_evidence`：保存来源文件、页码、章节/表格定位和原文证据。
- `structure_model_evidences`：连接结构模型与同 revision Evidence，禁止跨论文或跨 revision。

## 状态转换

```text
discovered -> needs_review -> valid -> confirmed -> persisted
                    |             |
                    v             v
                 blocked       excluded
```

- `discovered`：来源识别出可能的结构字段。
- `needs_review`：字段缺失、冲突或需要用户核对。
- `valid`：结构完整且 ASE 校验通过，但尚未确认。
- `confirmed`：用户明确接受该候选。
- `blocked`：不能安全生成结构。
- `excluded`：用户明确排除，不进入正式提交。
- `persisted`：随论文当前 revision 成功写入正式实体。

## 等价与合并

候选只允许在同一材料状态条件内比较。比较前生成 primitive/conventional 派生表示，并按元素、
晶胞长度/角度和周期性原子位置执行固定容差比较。等价时合并来源集合，不等价时保留多个候选
并写入 `conflicts[]`；禁止跨论文自动合并。
