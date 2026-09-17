# 本地材料检索

## 功能说明

从元素组合或化学式定位主业务数据库中的超导材料，并返回关联论文和物性记录。

## 当前行为

- Go API `POST /api/papers/search/records` 支持 `formula_search`、`elements_exact_search`、`elements_combination_search` 和 `elements_contained_search` 四种模式。
- 化学式检索通过化学式提取元素并构建 `system_key`；元素检索在 `chemical_systems` 内按精确、组合或包含关系匹配材料体系。
- 本地检索的记录主体是 `property_records`，关联 `property_modules`、`material_states`、`superconductors` 与当前 revision 的 `papers`；只读取 `property_code = tc` 的测量或预测 Tc 记录。一行代表一个材料在一组条件下的一条 Tc 记录。（[Issue #57](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/57)）
- 筛选条件各自对应真实列：Tc 使用 `property_records.value_number`，缺失时取 `value_min` 与 `value_max` 的均值，压强用 `material_states.pressure_value_gpa`，元素用 `material_states.superconductor_id`，关键词匹配论文字段或 `superconductors.chemical_formula`。（[Issue #57](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/57)）
- 请求的 `superconductor_type` 参数当前落到 `material_states.state_kind`，但该列的取值是 `theoretical`/`experimental`/`mixed`/`unknown`，描述数据来源性质而非材料分类；材料分类维度现为论文级 `paper_material_families` 关联。本地检索尚未按该关系筛选，属待核验的语义不一致。（[Issue #72](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/72)、[Issue #79](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/79)）
- 图表可见性（`chart_only`）筛选使用 `property_records.is_representative = true`。（[Issue #57](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/57)）
- 只返回 `papers.review_status = approved` 的记录，这是公开数据边界。
- `/search` 页面仅查询本地数据，支持分页、Formula/关键词、Tc 范围、压强范围、年份范围、超导类型、审核状态和图表可见性筛选；默认每页 50 条。
- Go 层对本地搜索结果使用完整请求体的 SHA-256 生成缓存键，筛选及分页参数均参与缓存。
- 选中元素后可进入对应 `/systems/:systemKey` 体系讨论，例如 Hg。该入口使用选中元素的精确组合，不改变检索模式；评论、弹幕和公开论文列表见[社区交流](../06_Researcher_Community_Forum/community-discussion.md)。

## 工作流程

用户选择元素或输入化学式，前端构造搜索模式和筛选参数；Go API 查询 `ChemicalSystem` 与 `Superconductor` 取得候选材料 ID；再以 `property_records` 为主体 JOIN `material_states`、`superconductors` 与 `papers`，返回年份、化学式、类型、压强、代表 Tc、空间群、数据来源、审核状态和 DOI 等字段。

## 约束

- 查询语义依赖 Go 侧简化的化学式元素提取规则，不等同于完整化学式解析器。
- 当前 Go 侧本地检索按 `papers.year DESC, property_records.id ASC` 排序；前端演示中对“代表 Tc 降序”的产品期望不等同于当前已实现后端排序。
- 本地结果的 `space_group` 取 `material_states.reported_space_group_symbol`（无值时为 `-`），不再是固定占位；但它仍只是展示列，空间群筛选未实现。（[Issue #57](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/57)）

## 代码与测试

- 入口：`frontend/src/pages/SearchPage.tsx`
- API：`goserver/handlers/papers.go`
- 路由：`goserver/main.go`
- 模型：`goserver/models/models.go`、`backend/models.py`
- 测试：`tests/03_data_search_and_database_discovery/`

## 相关变更记录

- [维护事项 #104：数据源退役规格](../../specs/104-retire-external-datasets/spec.md)与[验收记录](../../specs/104-retire-external-datasets/quickstart.md)。

- [Issue #57：修复论文详情页字段缺失与恒零值，记录搜索主体迁移到 tc_results](../../specs/57-paper-detail-data-parity/spec.md)

## 已知问题

- 本地空间群筛选未实现，前端不显示空间群范围筛选；结果表格的空间群列继续保留。
- `superconductor_type` 筛选按 `state_kind` 过滤，与论文级 Material family 的用户预期不符；社区图表侧已迁到 `paper_material_families`，本地检索的取值集合与前端 `SC_TYPE_MAP` 展示映射均未同步。（[Issue #72](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/72)）
