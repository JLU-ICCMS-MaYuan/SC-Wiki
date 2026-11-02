# 资讯接口

GET /api/news/feed 保持现有参数、总数、排序、来源和分页。每条追加：
- paper_type：experimental/theoretical/review/null。
- theoretical_subtype：calculation/method/theory/null，非 theoretical 为 null。
- material_families：[{id, name_zh, name_en}]，缺失为 []。

尚未分类、失败和输入过期时三维均为空。不返回模型配置、密钥、后台尝试 token。读取不触发模型调用，家族名称来自数据库当前目录。

2026-11-02：取消period/week时间过滤，正式查询仅使用kind、page、page_size。旧调用附带period/week时作为不使用的额外参数忽略，一律计数和分页该类型全部已收录条目。响应不再包含period、week、week_end、timezone。

排序固定为published_at倒序、first_seen_at倒序、id倒序；日期字段及原精度保留，缺日期的记录排在有日期记录之后。前端每栏page_size=5，页码独立；不再存在本周/历史两套数据集。
