# 技术任务

Issue状态以GitHub为准，本文件只作实施拆解。依据[Spec](spec.md)及[Plan](plan.md)。

- [x] T001 全仓检索及精读旧要求和完整相关读写链，记录research.md；用户删除答复已保存。
- [x] T002 [US1] 加入来源版本重放／真实交接失败用例及反例，证明现状失败。
- [x] T003 [US1] 统一backend/ingest/property_evidence.py工作稿快照及相关入口，登记返修来源元数据并保留归纳依据；backend/api/rag.py初次交接显式保存待确认分类及作者角色。
- [x] T004 [US2] 修改EvidenceWorkflow/EvidenceRegion及下层信息提示组件，删除重复摘要组件，取消整包兜底和信息框；model_review仅返回当前字段相关source_ids；补四宿主交互及真实模型引用验证。
- [x] T005 [US1/US2/US3] 执行字段、表单、mutation、定向前后端及隔离真实事务验证；旧失败独立基线。
- [x] T006 [US3] 核对本机和授权清单，彻底删除旧CaH6及解析表单，核对论文271与原PDF。
- [x] T007 [US3] 从给定两份PDF正式新上传、真实RQ和模型解析，检查字段来源、保存重读及隔离提交退回；问题先回查。
- [x] T008 更新validation.md、Overview、#174清单和Issue；仅提交已验证任务文件。

## 依赖

T001→T002→T003；T004依赖T001，可独立验证；T005完成后T006→T007；T008依赖实际验证。共享文件串行修改，无代理并行写入。

真实整篇事务验收复用scripts/verify-upload-submit.py，新增--return-cycle覆盖两管理员原样退回、返修重开和轻量摘要；所有写入在MySQL外层回滚，文件及任务状态副本隔离，不代用户正式送审。

## 实际证据

T002～T005的失败／成功及独立旧失败见validation.md；T006清理及保护对象见data-model.md和assets/verification.json；T007最终新任务、9个参数来源、268条正式来源及两角色各288项保留证据见同一验证数据。T008的本地源码摘要与文档链接已核验，提交号回写Issue；未授权推送，远程Spec链接保持待验证，不据此关闭Issue。
