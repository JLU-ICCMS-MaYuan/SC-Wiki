# 实施任务

输入：[Spec](spec.md)、[Plan](plan.md)、[Research](research.md)、[数据](data-model.md)、[契约](contracts/extraction.md)。

- [x] T001 创建 #172 和本目录全部设计文档、归档 IMG-001；依据用户“执行”。
- [x] T002 [US1/US2] 在 tests/01_decentralized_uploading/ 新增格式、语义、表单名称及保存重开失败测试。
- [x] T003 [US2] backend/ingest/property_extensions.py、domain_extraction.py 接入新提取条件有界整理，calculation_methods.py 明确输出格式。
- [x] T004 [US1] 前端条件字段统一声子方法名称，保留人工名称与计算阶段身份。
- [x] T005 [US3] scripts/ 新增按字段验证入口，真实响应重放、CaH6 来源重新提取与隔离保存重读，记录实际范围。
- [x] T006 [US3] AGENTS.md 固化字段回归规则；完成后台、前端与构建验证。
- [x] T007 回写 docs/overview/、本目录 validation.md 和 Issue，检查后仅提交任务文件，不推送。

## 覆盖与顺序

T002～004 对应 FR-001～005/SC-001～004；T005～006 对应 FR-006～007/SC-005。准备→失败测试→修复→实测→文档→本地提交。相同文件串行修改。先完成本次字段闭环，再考虑其他范围；不加入未授权增量。

T002～T006 依据：validation.md 的修改前后测试、固定响应重放、live-3 和 AGENTS.md。T007 的本地提交以包含本文件的 Git 提交为准；远程链接不由本地任务勾选代替。

## 完整解析恢复

- [x] T008 按用户新授权执行F001～F004，恢复原CaH6任务并完成全流程及字段收尾验证；证据见full-run-validation.md。
