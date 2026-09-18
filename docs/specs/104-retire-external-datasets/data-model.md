# 数据边界

## 保留事实来源

- `papers` 保存论文与 revision、审核状态；公开查询只允许已批准论文。
- `chemical_systems` 与 `superconductors` 保存元素体系和具体材料。
- `material_states` 保存状态条件，`property_modules` 和 `property_records` 保存物性；Tc 从规范 Tc 固定列读取。
- `structure_models` 保存结构文本，与物性记录分开读取。

本项不新增字段、实体、唯一性约束或生命周期，也不更改证据、revision 与权限关联。

## 退役应用模型

删除 `AlexandriaEntry`、`AlexandriaElementIdx`、`HTSCMaterial` 的应用定义与查询引用；旧表不再构成本地检索依赖。数据库中若仍有历史表，不在本项删除或迁移。

## 前端状态

删除可变数据源状态、跨来源适配与专属详情分派。检索模式、元素、化学式、筛选、页码、选中论文及结构状态继续归 SearchPage 管理。
