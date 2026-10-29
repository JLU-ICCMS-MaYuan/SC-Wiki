# 数据模型与所有权

关联：[Spec](spec.md) FR-003～011、FR-017、FR-020。

| 对象 | 现有事实来源 | 身份和本次用途 |
| --- | --- | --- |
| 论文 | papers | id及当前content_revision；公开须approved且approved_revision一致；论文视图归并单位 |
| 材料状态 | material_states、superconductors | paper_id＋paper_revision＋state_key；沿现有id，不以显示字段全局合并 |
| 状态标志 | 化学式／材料名、pressure_value_gpa、报告空间群、structure_optimization | 显示及条件匹配；未知值保留，SSCHA与静态不混合 |
| 物性记录 | property_modules、property_records | 属于一个明确状态；多个Tc不增加状态数；有实际Tc过滤时使用相关存在条件 |
| 完整结构 | structure_models、paper_structural_records | 只读当前revision完整model；state_key可空；独立模型不等于状态 |
| 导航上下文 | 浏览器URL | 查询、筛选、view、各自页码、详情return；不写业务数据库 |

不新增持久表、迁移或科学字段，不重新提取。旧Tc记录接口可保留给未审计完的其他调用方；本次新搜索不以它为状态事实来源。后续若确认没有调用方，可另按有界清理执行，不能为退役UI顺带破坏图表。

论文命中集合是满足条件的状态来源与完整结构来源的并集，再按论文id去重；状态集合只来自实际状态。已关联模型在独立列表中排除。筛选在相应状态／结构上同时成立，不能先按论文关联后拼凑不同状态条件。

匹配、计数及分页基于未分页完整候选集合；显示的匹配状态数是本次查询命中数，不是论文全部状态数。结果仅保存轻量摘要，正文和完整模型继续由详情按权限加载。
