# 资讯接口

GET /api/news/feed 保持现有参数、总数、排序、来源和分页。每条追加：
- paper_type：experimental/theoretical/review/null。
- theoretical_subtype：calculation/method/theory/null，非 theoretical 为 null。
- material_families：[{id, name_zh, name_en}]，缺失为 []。

尚未分类、失败和输入过期时三维均为空。不返回模型配置、密钥、后台尝试 token。读取不触发模型调用，家族名称来自数据库当前目录。
