# 审核契约

## 界面

共享顺序：approved（通过）、pending（退回待审核）、rejected（拒绝）。中英文保留现有译文。
快速审核使用已保存数据；编辑页批准使用当前分类选择。状态不因进入已批准论文而自动选中通过。
提交期间禁用选择、意见、关闭和提交；失败不关闭弹窗，保留所选状态和意见。

## 请求

沿用 `POST /api/admin/papers/:id/review`。每次请求携带 status、comment、review_request_id。
仅 approved 携带 superconductor_kind、material_families（id/name）、material_states（正式状态 id、material_dimensionality、structure_families 的 id/name/is_primary）。
正式分类名称兼容 name/name_zh；正式结构家族关联先转换为选择值；待审提交快照沿用编辑页既有回填优先级。
缺少必要分类仍由既有后端校验拒绝。Evidence 409、自审 403、角色守卫、历史事件及发布响应语义不变。
批量审核行为不变，无新增 API、版本或持久字段。
