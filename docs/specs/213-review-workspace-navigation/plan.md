# 实施方案

## 数据所有权与设计
FR-001/002：正式papers的review_status／approved_revision继续决定公开数据。交接事件最新handoff.holder派生私有workflow_status：author→rejected，review→pending，published→approved；旧稿无合同沿正式状态。不写另一份状态、不修改数据库。
已批准稿的首次拒绝通过现有review-commit在论文行锁内捕获公开内容、记return交接并建立作者返修稿；未批准和已接手稿沿既有require_writer。无独立return接口。
Go列表批量读取当前页的小型交接头，私有列表与筛选使用相同派生规则；详情只对原上传者或管理员提供workflow_status，公开批准字段保持。
FR-003/004/005：标题组件测量真实溢出后启用Tooltip；AccountReviews接收compact/full参数，共享MyPapersList和AdminPage的pageSize/滚动容器；独立页签通过查询参数承接；AdminWorkspacePage路由壳负责选择完整工作区，AdminPage仅负责审核列表，不循环依赖宿主。
FR-006：编辑页持有统一权限状态，加载、焦点更新、来源组件报告结构化ApiError；同一manuscript_handed_off由宿主展示，其余错误各自保留；fieldset及写入口遵守同一失权状态。
FR-007/008：PaperMaterialsSection复用materialStateSummary，右侧固定容器折叠且内部滚动；点击按state_key在当前宿主找目标，兼容历史无key时的显式位置。用布局容器留出右侧宽度，保留研究材料来源标记，固定值由宿主提供，不扫描科学字段。
## 实施顺序与映射
T001文档与附件；T002失败回放；T003拒绝/公开版与私有状态；T004列表分页、标题和命名；T005权限合并；T006大纲及宿主布局；T007集成验证和Overview；T008任务内提交及Issue回写。
FR-001/002→US1→T002/T003→Python/Go存储回归及生命周期；FR-003/004/005→US2→T004→组件/浏览器；FR-006→US3→T005→完整宿主；FR-007/008→US4→T006→五入口定位、表单/变异门；SC-005→T007。
## 约束与回退
不更改来源数据、字段契约和模型调用。失败保留输入及旧公开版。只删除本轮废弃的独立交还操作，旧交接历史保留可读。共享文件逐项核对，任务代码可通过反向本次补丁回退，不清理用户草稿。
