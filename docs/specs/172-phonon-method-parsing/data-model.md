# 数据约定

继续使用材料状态 → 超导性质记录 → payload.calculation_conditions.extensions 数组。声子方法记录 key=electron_phonon.phonon_method、value_kind=text、value_raw=原报告值；来源留在现有 evidences／source_associations。名称为显示语义，不更改 key 与记录归属。

仅新提取入口把已识别分组转为上述数组；缺失不创建科学值。空 extensions 允许转换为 []。人工 name_raw 和历史来源不批量重写。无新数据库表、列、公共接口或版本迁移。
