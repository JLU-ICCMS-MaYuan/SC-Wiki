# 技术任务：默认启用人工问题窗口并以最小改动接入新文献解析

输入：[规格](spec.md)、[计划](plan.md)、[调研](research.md)、[数据模型](data-model.md)及接口契约。任务只描述技术拆解，协作状态以Issue为准。实施进度与具体证据见validation.md；完整文献验收和远程文档门单列，不以复选框代替事实。

## 准备、用户故事及验证

- [x] T001 [US1] 在tests/01_decentralized_uploading/human-questions-integration.test.tsx和backend/tests/test_human_question_integration.py加入正式宿主接线、版本和无题零额外调用反例。
- [x] T002 [US1] 串行修改backend/ingest/upload_jobs.py、backend/ingest/upload_contracts.py、backend/api/upload_tasks.py及frontend/src/lib/paperProcessing.ts，连接真实问题摘要和答案调度。
- [x] T003 [US2] 修改backend/rag/config.py增加默认true单一开关，任务策略与服务端能力一致；不在本轮改.env或运行服务。
- [x] T004 [US2] 在frontend/src/components/UploadModelActivity.tsx、frontend/src/pages/UploadPage.tsx及frontend/src/components/UploadParsingDetail.tsx正式挂载问题组件，补frontend/src/i18n/zh/upload.ts和frontend/src/i18n/en/upload.ts。
- [x] T005 [US2] 在backend/tests/test_human_question_integration.py验证等待/恢复计时、清理保留、关闭旧题可答、模型引用保留与代次；执行三项契约及构建。
- [ ] T006 [US1] 直接使用用户实际提供的新文献在明确的测试环境验证问题→其他字段继续→答案→局部恢复→保存重读；将实际后续业务及未覆盖范围写入本目录validation.md，不做同文献开关对照。
- [x] T007 [US1] 实施验证后回写docs/overview/01_Decentralized_Uploading_of_Superconductivity_Data/pdf-parsing-pipeline.md、README.md和docs/specs/174-form-processing-contract/form-inventory.md，按Documentation Impact收尾。

## 依赖与执行顺序

上游依赖为目标3。先故障回归再实现，模型调用在保存事务外，完成当前单元后才接下游；共享文件顺序遵守[计划](plan.md)。技术草案未确认及远程文档门未满足时不以本任务表启动实施。

## 需求覆盖

FR/SC、设计、任务与验证的逐组映射见[plan.md的需求到设计及任务映射](plan.md#需求到设计及任务映射)。任务勾选须附实际生产路径证据，不以Mock关键边界或静态字符串断言代替交互。

## 最小交付与后续增量

先完成本目标P1用户故事，再按本轮四目标依赖接线；不增加未经讨论的目标，不用局部完成代替全链验收。


## 本轮实施证据与剩余边界

已勾选项对应validation.md的实际源码、固定回归、SQL/RQ/HTTP及宿主交互；新增问题面板实际交互位于tests/01_decentralized_uploading/human-questions.test.tsx。真实新文献题目→第二次Worker→交接/业务结果继续留证，未发生的场景不计通过。未推送，远程文档门不勾选，不自动关闭Issue。
