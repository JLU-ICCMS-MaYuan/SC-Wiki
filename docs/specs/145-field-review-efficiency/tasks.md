# 技术拆解（草稿）

依据：[spec.md](spec.md)、[plan.md](plan.md)、[audit.md](audit.md)。Issue是未完成行动的状态来源，本文件不维护另一份协作状态。

- [x] T001 [US1] 使用tools/audit_fields.py读取当前preflight，导出assets/field-audit.json并核对447单元、518入口，保留计数口径与未知项。
- [x] T002 [US1] 建立field-catalog.md、assets/editable-fields.csv与assets/field-review-map.fragment.html，归档IMG-001，使用tools/verify_map.mjs验证窄屏和逐项切换。
- [ ] T003 [US1] 与用户逐字段审查并将已确认意见追加spec.md，保持原话，不将未讨论建议标为通过。
- [ ] T004 [US2] 依确认结果细化frontend/src/components/EvidenceWorkflow.tsx、UploadTaskEditor.tsx及backend/api/evidence.py的局部保存合同与设计，再实施无变化短路和当前字段返回。
- [ ] T005 [US3] 依确认结果细化backend/ingest/scientific_evidence.py、evidence_proposals.py、manual_evidence.py的历史按需/当前凭证读取与失效合同，再实施；不得先建立复杂缓存框架。
- [ ] T006 [US2] 在tests/01_decentralized_uploading中建立实际“完成/人工说明保存”性能轨迹，区分无修改、改值、仅理由、附件、并发，记录耗时、请求与读写量。
- [ ] T007 [US3] 在tests/01_decentralized_uploading验证来源/规则变化、真实冲突、空字段、权限及重复请求反例，对比性能，结果写validation.md。
- [ ] T008 更新docs/overview/01_Decentralized_Uploading_of_Superconductivity_Data/source-association-review.md中的已实现行为，补远程文档验证后回写Issue；不自动推送。

T001/T002的证据见validation.md与对应制品；只完成文档审计。顺序为T003→设计确认→T004/T005→T006/T007→T008，实际代码实施需要后续授权。US2可先验证无修改零写入，US3独立验证历史/来源变化。当前不宣称实施完成。

- [x] T009 [US1] 对照EvidenceFieldMarkers、EvidenceWorkflow及后端状态转换，建立red-marking.md，补原路径图的原因区；实调用evidenceProblem核查15个代表状态，不修改产品逻辑。
