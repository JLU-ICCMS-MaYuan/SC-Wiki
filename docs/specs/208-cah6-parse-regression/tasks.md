# 已完成工作与验证映射

**输入**：[spec.md](spec.md)、[plan.md](plan.md)、[research.md](research.md)、[data-model.md](data-model.md)、[接口约束](contracts/behavior.md)。

本表为`b1fc93be`的技术追记，不授权再次修改代码或清理现场；每项完成依据均由[validation.md](validation.md)及既有精简报告支持。

## 准备与旧要求审查

- [x] T001 对照`docs/overview/README.md`及既有#176/#183/#194/#203/#204/#205规格，索引全仓并精读故障命中调用链；依据为原现场记录“审查方法”。

## 用户故事1：完成状态与合法字段

- [x] T002 [US1] 先用`tests/01_decentralized_uploading/test_scientific_form_filling.py`等固定回放检出失败，再在`backend/ingest/scientific_form_filling.py`恢复服务器分组装配边界（FR-001）。
- [x] T003 [US1] 在`backend/ingest/model_review.py`补合法空软件组，使用`test_unified_model_review.py`验证不覆盖原值（FR-002）。
- [x] T004 [US1] 在`backend/ingest/upload_jobs.py`统一完成状态，用`test_parsing_preview_sync.py`验证失败留预览、成功才ready（FR-003）。
- [x] T005 [US1] 在`backend/ingest/evidence_proposals.py`和`backend/ingest/property_field_review.py`复用已登记类型，运行`tests/01_decentralized_uploading/test_registered_review_types.py`（FR-007）。

## 用户故事2：结构与当前页面

- [x] T006 [US2] 在`backend/ingest/structure_extractor.py`补晶胞表及设置读取，用`backend/tests/test_structure_extractor.py`和真实原PDF验证（FR-005）。
- [x] T007 [US2] 在`backend/ingest/material_state_contract.py`、`backend/ingest/canonical_structure.py`及`backend/ingest/model_review.py`统一归属前身份，运行`tests/01_decentralized_uploading/test_parsing_state_identity.py`及结构归属回归（FR-006）。
- [x] T008 [US2] 在`backend/ingest/scientific_evidence.py`、`backend/ingest/model_review.py`、`backend/ingest/property_evidence.py`和`backend/services/manuscript_handoffs.py`传入并剥离临时结构输入，运行`tests/01_decentralized_uploading/test_structure_review_input.py`（FR-009）。
- [x] T009 [US2] 在`backend/ingest/material_state_contract.py`、`backend/api/rag.py`及`backend/ingest/model_review.py`共用当前材料汇总，在`backend/ingest/evidence_proposals.py`保持其派生只读语义（FR-010）。
- [x] T010 [US2] 在`backend/api/evidence.py`摘要复用派生规则，以`test_field_decisions_mysql.py`结构场景及真实Chrome证明0误标红和文件变更失效（FR-011）。

## 用户故事3：保存、清理与持久版本

- [x] T011 [US3] 在`backend/ingest/scientific_evidence.py`清理对应工作稿及来源使用关系，以`test_upload_workdraft_cleanup.py`和真实备份清理验证（FR-004）。
- [x] T012 [US3] 在`backend/ingest/model_review.py`复用同值规范化，运行`test_registered_review_types.py`数值场景（FR-008）。
- [x] T013 [US3] 在`backend/api/evidence.py`投影后排序，使用真实大型表单完整提交重读验证（FR-012）。
- [x] T014 [US3] 在`backend/services/spectra.py`重读首次持久body，以`test_spectrum_initial_workdraft_mysql.py`验证往返一致及真实压力变化（FR-013）。

## 跨故事验收与记录

- [x] T015 从两份用户原PDF重新HTTP上传、RQ完成33批核对，运行`test:field-contract`、`test:form-contract`、`test:form-contract:mutation`及受影响回归；依据为原报告的parse/regression（SC-001、SC-002、SC-006、SC-007）。
- [x] T016 实际浏览器检查新稿，并用`scripts/verify-upload-submit.py`进行完整提交、两角色批准、来源和快照重读、重复提交外层回滚；依据为原报告browser/submit_rollback/protection（SC-003、SC-004、SC-005）。
- [x] T017 补建`docs/specs/208-cah6-parse-regression/`，复用既有证据；记录分类、限制和文档发布边界。本项证明建档，不冒称远程链接已通过。

## 依赖与覆盖

T001在其他实现前执行；同一后端文件上的改动串行。T002—T014完成后才进行最终重新上传和T015—T016；T017为本轮追记。路径缩写与[plan.md](plan.md)一致。

FR-001—FR-013分别由T002、T003、T004、T011、T006、T007、T005、T012、T008、T009、T010、T013、T014覆盖；SC-001—SC-007由T015—T016及[验收表](validation.md#验收映射)覆盖。没有新增待实施功能；尚未完成的远程发布核验仅在Issue及需求检查表记录。
