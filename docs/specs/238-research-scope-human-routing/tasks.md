# 技术任务：按本文实际研究对象解析结构并识别必须人工裁定的科学问题

输入：[规格](spec.md)、[计划](plan.md)、[调研](research.md)、[数据模型](data-model.md)及接口契约。任务只描述技术拆解，协作状态以Issue为准。代码、模型和真实业务验证任务全部未执行。

## 准备、用户故事及验证

- [ ] T001 [US1] 在backend/tests/test_tc_material_scope.py及backend/tests/test_research_scope_routing.py加入无Tc/仅范围/引用/跨段反例，证明旧排除行为失败。
- [ ] T002 [US1] 修改backend/ingest/tc_material_scope.py和backend/ingest/parsing_workflows.py的本文对象范围协议；保留范围原文，不改标准键。
- [ ] T003 [US1] 串行接入backend/ingest/structure_reading.py、backend/ingest/state_inventory.py和backend/ingest/upload_jobs.py，使结构保留贯通所有保护入口。
- [ ] T004 [US2] 在backend/tests/test_research_scope_routing.py补自纠/真实冲突/合法未报告/技术失败及代码指令反例。
- [ ] T005 [US2] 增加backend/ingest/human_question_routing.py并在backend/ingest/model_review.py投影已有核对事实；不新增独立分类模型。
- [ ] T006 [US2] 执行受影响原PDF新提取、归一化、规划、保存重读及三项契约，证据写入本目录validation.md；不使用旧答案冒充新提取。
- [ ] T007 [US1] 实施后同步docs/specs/211-state-first-spectra/spec.md、docs/specs/227-scientific-chart-reading/spec.md及解析Overview的已验证替代范围。

## 依赖与执行顺序

上游依赖为目标1。先故障回归再实现，模型调用在保存事务外，完成当前单元后才接下游；共享文件顺序遵守[计划](plan.md)。技术草案未确认及远程文档门未满足时不以本任务表启动实施。

## 需求覆盖

FR/SC、设计、任务与验证的逐组映射见[plan.md的需求到设计及任务映射](plan.md#需求到设计及任务映射)。任务勾选须附实际生产路径证据，不以Mock关键边界或静态字符串断言代替交互。

## 最小交付与后续增量

先完成本目标P1用户故事，再按本轮四目标依赖接线；不增加未经讨论的目标，不用局部完成代替全链验收。
