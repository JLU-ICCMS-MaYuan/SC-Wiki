# 实施任务

输入：[Spec](spec.md)、[Plan](plan.md)、[研究](research.md)、[数据](data-model.md)、[接口](contracts/review.md)。按依赖顺序实施，复选框只在生产路径和对应验证完成后勾选。

- [x] T001 建立docs/specs/147-two-stage-field-review完整文档并核对Issue类型、原话和关联。
- [x] T002 在backend/ingest/property_field_review.py、scientific_evidence.py、field_review.py实现独立键和稳定复用；增加tests/01_decentralized_uploading/test_two_stage_review.py。
- [x] T003 [US1] 在backend/api/evidence.py及现有草稿存储实现统一局部保存、版本检查、原始输入、说明和定向读取。
- [x] T004 [US3] 在backend/ingest/property_evidence.py、upload_jobs.py收拢解析并实现任务去重、逐字段科学判断、技术失败与一致性异常保护。
- [x] T005 [US2] 在frontend/src/components/EvidenceWorkflow.tsx、EvidenceFieldMarkers.tsx拆开入口、摘要/历史与主动模型核对。
- [x] T006 [US1] 在frontend/src/components/UploadTaskEditor.tsx及共用表单取消编辑重核、无变化写入与连带红框，保存中间输入。
- [x] T007 [US3] 在backend/api/rag.py、backend/services/paper_revisions.py和goserver/handlers/paper_evidence.go接入统一严格门禁及原子版本校验；前端提交冻结并自动完成。
- [x] T008 在tests/01_decentralized_uploading覆盖全部SC，运行MySQL回滚、浏览器与447项性能验证，写validation.md。
- [x] T009 用Overview技能回写已实现行为，README操作说明、Issue证据和任务范围本地提交；不推送。
- [x] T010 [US2] 修复字段设置分项展示回归、μ* 设置字段定位和待审核状态冒充 AI 理由；使用真实设置组件路径补回归测试并追加验证记录。
- [x] T011 [US2,US3] 修复主动核对版本循环、保存当前人工依据并评价无证据理由，持久通过后提交复用；验证真实摘要/排队接口、并发拒绝、模型输入、依据版本及持久结果读取。证据见 validation.md 的主动核对回归节。
- [x] T012 更新三个模型入口流程图与无理由人工认可规则；保留原话和旧选择替代记录，归档截图，同步 Issue 与 Spec。仅文档验收。
- [ ] T013 [US2,US3] 实施正式逐字段人工通过／不通过及版本绑定；认可分支无理由输入、零模型请求；处理本字段旧候选待选标记，保留历史（FR-011,015 / SC-006,010）。
- [ ] T014 [US1,US2] 将原文、AI 理由、审核按钮放在一起，人工修改记录中仅“保存”；明确来源加载中／失败／空／旧版本，保护同版本详情（FR-013,014 / SC-008,009）。
- [ ] T015 [US3] 三入口统一识别人工通过、模型通过、免审、待核对修改、同版本失败和未处理问题；提交只在 LLM ② 条件下启动模型（FR-012 / SC-007）。
- [ ] T016 用真实页面、接口与持久化往返验收新流程；覆盖模型调用计数、无关字段隔离、并发和来源显示；通过后再更新当前功能总览，不把 T012 当实现完成。

## 覆盖与依赖

T001→T002→T003/T004→T005/T006→T007→T008→T009。FR/SC完整映射见plan.md；不把文档完成当成业务完成。先完成基础再贯通US1、US2、US3，最终逐项检查完整原始计划。
