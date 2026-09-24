# 公开论文统计接口

`GET /api/community/publication-stats`，无需登录，不改变现有贡献接口。

## 输入

可选 `refresh=true|false`；缺省为 false；其他值返回 400。无分页或家族筛选：返回完整同一快照。

## 成功响应

```json
{
  "families": [
    {"family_id": 2, "name_zh": "铜基超导体", "name_en": "Cuprate", "paper_count": 3, "unknown_year_count": 1, "years": [{"year": 2020, "paper_count": 1}, {"year": 2021, "paper_count": 0}, {"year": 2022, "paper_count": 1}]},
    {"family_id": 0, "name_zh": "未分类", "name_en": "Unclassified", "paper_count": 0, "unknown_year_count": 0, "years": []}
  ],
  "generated_at": "2026-09-24T00:00:00Z"
}
```

时间使用带时区格式，数组不返回 null。目录名按已有双语回退规则展示；未分类使用界面字典。

## 错误与生命周期

400：非法 refresh 参数；500：数据库聚合失败；响应均为 `{"error":"说明"}`，不返回 SQL 或部分统计。
Redis 不可用时仍查询数据库。公共快照键 `community:publication-stats:v1`，TTL 一小时；手动刷新重建完整快照。数据修改最多延迟一小时或由手动刷新体现，本期不增加审核写链路耦合。

## 页面契约

初次加载年度区隐藏；家族整列支持鼠标及键盘点击，当前选中高亮。点击当前家族或收起按钮关闭，切换家族替换同一区域。年度图横轴为发表年份，纵轴为篇数。0 篇列仍有可操作名称。切换及展开不再次请求接口。
