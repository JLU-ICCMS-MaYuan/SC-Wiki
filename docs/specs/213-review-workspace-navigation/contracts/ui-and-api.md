> **拆分前历史材料（2026-11-04）**：本目录原六目标已独立迁入六个子Issue及Spec。本文保留原实施记录，不再作为#213 Epic的活动Feature规格或任务入口。当前文档见[拆分导航](../README.md)；业务实现和既有验证不因拆分而重跑。

# 界面与接口契约

- POST /api/rag/evidence/review-commit：status=rejected是唯一返修交接触发。已公开且当前已发布的稿件允许其他合法审核员拒绝；普通/原上传者不可操作。其他归属仍检查当前经手人。
- /api/rag/handoffs只读，移除POST /{paper_id}/return；GET不再返回can_return。
- 私有论文列表/详情可返回workflow_status；私有筛选review_status使用工作稿派生状态。正式review_status仍反映公开图，不被未批准稿覆盖。
- 个人页检查区pageSize=3，无内部滚动；独立检查工作区pageSize=20且内部滚动，review_tab=history|pending承接页签。分页和筛选显式请求，旧响应不得覆盖新响应。
- 失权错误manuscript_handed_off在宿主标题下唯一展示“稿件已交出，当前账号没有编辑权。”；其他错误正常显示。
- 大纲条目由当前宿主状态生成，缺失明确提示；点击只展开/定位，不触发保存、审核、重新提取或模型。
