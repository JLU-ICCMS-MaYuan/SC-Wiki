# 数据与状态

不新增持久表或列。

- 论文：`papers.id` 去重；`year` 是发表年份；`review_status` 决定公开；`content_revision` 决定家族版本。
- 家族目录：`material_families.id/name_zh/name_en` 提供所有分类及名称；不返回创建人或内部 code。
- 论文家族：`paper_material_families(paper_id, paper_revision, material_family_id)` 多对多；只读当前版本。
- 年度项：`year` 为 1–9999，`paper_count` 为非负整数；升序且中间补零。
- 家族统计：`family_id/name_zh/name_en/paper_count/unknown_year_count/years`。0 为合成未分类项，始终提供；`paper_count = sum(years.paper_count) + unknown_year_count`。
- 快照：`families` 全量数组及 `generated_at`；降序篇数、升序家族 ID。零篇目录项保留，年度数组为空。

客户端保存单份快照、当前选中家族 ID、加载及错误状态。初始选中为空；点击当前 ID 清空，其他 ID 切换；刷新保持仍存在的选择，失败保留旧快照。选中零篇或全部年份未知家族展示文字，不绘制无意义年度数据。
