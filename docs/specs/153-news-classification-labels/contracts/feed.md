# 资讯接口

GET /api/news/feed 保持现有参数、总数、排序、来源和分页。每条追加：
- paper_type：experimental/theoretical/review/null。
- theoretical_subtype：calculation/method/theory/null，非 theoretical 为 null。
- material_families：[{id, name_zh, name_en}]，缺失为 []。

尚未分类、失败和输入过期时三维均为空。不返回模型配置、密钥、后台尝试 token。读取不触发模型调用，家族名称来自数据库当前目录。

新增 period=week/history/all（旧调用默认 all，页面显式 week）。week=YYYY-MM-DD 可固定一个不晚于当前周的周一；非法日期、非周一或未来周返回 400。自然周使用 Asia/Shanghai，条件为 date_precision=day 且时间落在周一零点至下周一零点的半开区间；history 是该条件的补集。计数与分页使用同一条件。响应追加 week、week_end、timezone 和 period。
