# 数据模型：浅度论文

## 所有权与保存

- 任务：defer_parsing、parsing_mode（shallow/deep）、程序管理的 _parsing_workflow；模式在上传完成入队时固定，恢复保持。
- 草稿：复用 paper 与空 material_states；浅度流程绑定程序管理，浏览器不能替换。标准科学键和摘要不改。
- 正式论文：review_status=published；content_revision 保持正式版本，approved_revision、reviewed_by_user_id、reviewed_at 均为空。
- 历史：仅 uploaded 事件；upload_submission 保存流程绑定、论文级分类及作者角色，不能生成 reviewed 事件冒充人工批准。
- chemical_systems：当前论文及 revision 下，从研究材料清单严格解析得到的元素集合索引；没有 superconductor、材料状态、物性或结构实例。
- 文件及文本：沿现有 paper_files、paper_chunks 与 Document IR 持久化；原文件仍可访问。

## 约束与迁移

扩展 ck_papers_review_revision，published 只允许 approved_revision 为空；原 approved 必须匹配 content_revision 的约束保持。
迁移从既有 20261106_0225 分支追加；其他已存在迁移分支不自动合并或执行。只在隔离环境验收。
降级发现 published 论文时拒绝继续，避免把直接收录转换为审核结论。
