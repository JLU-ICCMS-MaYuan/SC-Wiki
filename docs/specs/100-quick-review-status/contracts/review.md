# 审核契约

## 界面

共享顺序：approved（通过）、pending（退回待审核）、rejected（拒绝）。中英文保留现有译文。
快速审核使用已保存数据；编辑页批准使用当前分类选择。状态不因进入已批准论文而自动选中通过。
提交期间禁用选择、意见、关闭和提交；失败不关闭弹窗，保留所选状态和意见。

## 请求

沿用 `POST /api/admin/papers/:id/review`。每次请求携带 status、comment、review_request_id。
仅 approved 携带 superconductor_kind、material_families（id/name）、material_states（正式状态 id、material_dimensionality、structure_families 的 id/name/is_primary）。
正式分类名称兼容 name/name_zh；正式结构家族关联先转换为选择值；类型和维度取当前正式详情。仅首次 pending 且正式论文家族为空时，回填提交快照的家族候选；结构家族按 state_key 或历史唯一化学式匹配，保留已有结构关联并补齐未落库候选。保存后不得覆盖已保存或已清空的结构家族，也不回填 unknown 分类。材料状态使用各自正式 ID，不按快照顺序拼接。快照读取的 404 回退与其他错误阻断保持不变。
缺少必要分类仍由既有后端校验拒绝。Evidence 409、自审 403、角色守卫、历史事件及发布响应语义不变。
批量审核行为不变，无新增 API、版本或持久字段。

## 管理员科学保存

沿用 `PUT /api/rag/papers/:id/scientific-draft`。管理员/超级管理员可保存自由输入的 pending 家族，服务端解析或创建目录并保存关联；上传者不获得创建权限。材料家族为空仍返回 `material_family_required`，结构家族可为空。快速批准首次家族先经本接口保存后重新读取分类，再执行证据门禁；失败不发送批准请求。
