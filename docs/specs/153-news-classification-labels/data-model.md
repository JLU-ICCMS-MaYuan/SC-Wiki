# 数据模型

news_feed_classifications：item_id 主键且引用 news_feed_items，删除级联；paper_type、theoretical_subtype 可空；content_hash、catalog_hash、rule_version、model、reason；status（running/completed/failed）、attempts、attempt_token、updated_at。约束仅允许三种类型与三个理论子类，非理论子类必须为空。

news_feed_material_families：(item_id, material_family_id) 联合主键；资讯删除级联，材料家族删除受限制。只关联已有 material_families。

content_hash 为 UTF-8(title + NUL + summary) 的 SHA256，Go 使用同算法。目录指纹由按 ID 排序的目录及排序后的别名生成，不包含更新时间等无关字段。输入和规则未变的 completed（包括全空结果）不重试。
