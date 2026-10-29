# 检索结果接口草案

关联：[Spec](../spec.md) FR-002～012、FR-017～019；事实所有权见[数据模型](../data-model.md)。这是拟实现契约，当前服务器尚无此端点。

## 新接口

`POST /api/papers/search/results`，由Go主业务API读取当前主库，不通过一页旧Tc记录凑结果。

请求保留elements、mode、formula、keyword、压强／年份及实际启用的既有筛选字段，增加view（papers或states）、limit和offset。默认view=papers，limit=20，上限100，offset非负。未知view按文档规则归一，非法元素／范围给明确参数错误。具体科学类型筛选在实施前按Research核对真实字段，不把state_kind当材料家族。

响应结构：

```json
{
  "view": "papers",
  "items": [],
  "total": 1,
  "papers_total": 1,
  "states_total": 8,
  "limit": 20,
  "offset": 0
}
```

示例total为固定夹具的预期值，不代表当前接口已存在。view=papers的items为论文摘要（paper_id、revision、标题、年份、期刊、DOI、匹配状态数、匹配材料）；view=states为状态摘要（state_id、state_key、paper_id、revision、材料名／化学式、压强、报告空间群号／符号、优化条件、来源论文摘要、可用结构引用）。完整正文、原子坐标不在列表响应重复发送。

公开候选必须属于approved且approved_revision=content_revision的论文；结构只读同revision的retained完整model。状态身份不跨论文去重。

论文计数包含无状态完整结构的来源；状态计数不包含虚构的模型状态。同一状态的多条Tc／其他物性不增加states_total。同一论文既有状态又有模型只计一次。排序应有稳定尾键：论文按年份降序、paper_id；状态按论文排序、压强、优化条件、state_key／id。未知压强位置固定。

同一候选应同时满足材料条件，拒绝跨状态拼接。先形成完整集合与COUNT DISTINCT再分页，返回页数与total单位一致。无结果items为空且total=0；数据库或结构表不可用返回明确错误，不能伪造为0。

## 独立结构区

沿用 `/api/rag/structural-records/search` 的详情权限、模型与来源表示；新页面需通过服务端先排除state_key已关联项再计数／分页，不能在当前页前端过滤后沿用未过滤total。实施选择扩展现有接口独立项过滤参数或给出等价未分页候选查询，保持已有消费者不受影响。论文聚合查询仍以完整结构来源集合参与去重，而非依赖该区域当页items。

## 请求生命周期

筛选防抖沿原合理触发，切换view即时更新当前页请求；请求标识／取消保证旧响应不覆盖新query或view。服务不新增科学数据写入、AI调用或业务库回填。

## 兼容与验证

旧 `/search/records` 调用方先审计；本Feature只移除搜索UI依赖，不自动删除图表等仍使用契约。新增Go查询必须有多状态、多Tc、无Tc、无状态模型、跨页／过滤／revision／审核权限集成用例。涉及MySQL去重和分页的SQL必须在隔离MySQL验证，单纯SQLite或字符串断言不够。
