# 技术任务：支持解析人工问题追加排队、字段暂挂与回答后局部恢复

输入：[规格](spec.md)、[计划](plan.md)、[调研](research.md)、[数据模型](data-model.md)及接口契约。任务只描述技术拆解，协作状态以Issue为准。代码、模型和真实业务验证任务全部未执行。

## 准备、用户故事及验证

- [ ] T001 [US1] 在backend/tests/test_human_questions.py、backend/tests/test_material_batches.py加入追加/去重/前组待答后组继续与技术失败反例。
- [ ] T002 [US1] 增加backend/ingest/human_questions.py并串行接入backend/ingest/upload_tasks.py、backend/ingest/scientific_evidence.py：首题无草稿也先持久提交、再发缓存/响应。
- [ ] T003 [US1] 修改backend/ingest/material_batches.py，按稳定字段/记录记录部分完成、待答和真实依赖；有效结果原样复用。
- [ ] T004 [US1] 在backend/ingest/model_runtime.py与backend/ingest/upload_jobs.py增加安全点领取和paused人工等待，保存上下文后释放；不改503预算。
- [ ] T005 [US2] 在tests/01_decentralized_uploading/human-questions.test.tsx加入三入口、不答、发送失败、输入保留和重复点击交互。
- [ ] T006 [US2] 增加frontend/src/components/UploadHumanQuestions.tsx与backend/api/upload_tasks.py问题读答接口，按contracts/questions.md验证身份、权限和版本。
- [ ] T007 [US2] 串行接入backend/ingest/manual_evidence.py、backend/ingest/model_review.py、backend/ingest/field_decisions.py及backend/services/manuscript_handoffs.py，只向相关字段交接人工方向及证据，不自动批准。
- [ ] T008 [US2] 在backend/tests/test_human_questions.py和backend/tests/test_model_runtime.py验证首次无草稿/Redis丢失/重启/过期答案/多标签/重复继续/保存失败/旧执行隔离。
- [ ] T009 [US2] 运行三项契约、四宿主受影响交互、真实RQ暂停释放/恢复与大草稿局部渲染验证，证据写入本目录validation.md。
- [ ] T010 [US1] 实施后同步docs/specs/229-semantic-parallel-extraction/spec.md、docs/specs/230-paper-first-processing/spec.md和#174清单；侧栏及颜色只维护原唯一入口。

## 依赖与执行顺序

上游依赖为目标2。先故障回归再实现，模型调用在保存事务外，完成当前单元后才接下游；共享文件顺序遵守[计划](plan.md)。技术草案未确认及远程文档门未满足时不以本任务表启动实施。

## 需求覆盖

FR/SC、设计、任务与验证的逐组映射见[plan.md的需求到设计及任务映射](plan.md#需求到设计及任务映射)。任务勾选须附实际生产路径证据，不以Mock关键边界或静态字符串断言代替交互。

## 最小交付与后续增量

先完成本目标P1用户故事，再按本轮四目标依赖接线；不增加未经讨论的目标，不用局部完成代替全链验收。
