# 实施任务：文献类型流程选择

输入：[Spec](spec.md)、[Plan](plan.md)、[Research](research.md)、[数据模型](data-model.md)、[契约](contracts/workflow.md)。

## 准备与基础

- [x] T001 完成 `docs/specs/212-typed-parsing-workflow/` 文档、确认和需求覆盖核验。
- [x] T002 [US1] 先在 `backend/tests/test_parsing_workflows.py` 复现匹配/不匹配/未知/失败与副本隔离，实现 `backend/ingest/parsing_workflows.py`。（FR-001—004/006，SC-001/003）
- [x] T003 [US2] 在 `backend/ingest/upload_jobs.py` 接入通用读取、派发和暂停，`upload_tasks.py`/`upload_contracts.py`处理策略/状态/生命周期；补Worker入口测试。（FR-001—004，SC-001）
- [x] T004 [US3] 在 `backend/api/rag.py`、`backend/ingest/field_drafts.py`、`backend/services/paper_revisions.py`、`manuscript_handoffs.py` 等入口保护绑定与正式恢复；`tests/01_decentralized_uploading/test_workflow_binding.py` 验证SQL及缺失/伪造。（FR-005/007/008，SC-002）
- [x] T005 [US3] 在 `frontend/src/components/UploadParsingDetail.tsx`、`UploadTaskCenter.tsx`、`UploadTaskEditor.tsx` 和共享标识组件接入暂停/身份显示；补 `tests/01_decentralized_uploading/typed-parsing-workflow.test.tsx` 并同步表单清单。（FR-004—008，SC-002/005）

## 验证与收尾

- [x] T006 执行字段/表单/变异、受影响Python/Vitest回归及构建，记录 `validation.md`。（FR-007，SC-005；两项旧失败独立基线复现，15项旧MySQL测试跳过不作通过）
- [x] T007 隔离真实来源执行受影响解析与保存重读，在 `validation.md`记录源码、模型、来源及未验收项。（SC-004中的路由/相邻字段已验证；整篇及谱终态未在本项重验）
- [x] T008 增量回写 `docs/overview/` 的解析/字段映射/审核文档，核对任务独立提交范围；Issue远程链接未验证时保持OPEN。

## 依赖、覆盖与增量

- [x] T009 修复无章节小标题结果被误拦截：覆盖流程选择、理论二级分类、字段来源定位及交接重定位；真实原文重判与定向回归证据见 [验证记录](validation.md#无章节小标题的贡献依据修复2026-11-06)。（FR-001、SC-001、#128）

T001→T002→T003→T004→T005→T006/T007→T008。共享文件串行，不使用并行代理。US1/US2为最小路径，US3保持全生命周期一致后才宣称功能完成。全部FR/SC覆盖见Plan映射；技术复选框不替代Issue协作状态。
