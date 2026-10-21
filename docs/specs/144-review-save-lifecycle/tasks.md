# 实施任务

依据：[spec.md](spec.md)、[plan.md](plan.md)、[research.md](research.md)。用户已授权开始执行；技术完成不替代Issue协作状态。

- [x] T001 保留工作区基线于/tmp/scwiki144-implementation-baseline，核对spec.md原话与最新实施授权，明确最小后台方案。
- [x] T002 [US1] 在tests/01_decentralized_uploading/test_review_lifecycle.py添加空单位/未启用值槽、严格类型和身份反例。
- [x] T003 [US1] 修复backend/ingest/evidence_proposals.py保存合同及规则通过接受资格，执行对应回归。
- [x] T004 [US2] 在test_review_lifecycle.py及test_review_lifecycle_mysql.py复现Tc依赖、旧版本变化、技术失败与真实冲突。
- [x] T005 [US2] 修改condition_rules.py，新增condition_lifecycle.py并接入scientific_evidence.py，保留结果归属核对与历史审计。
- [x] T006 [US3] 在tests/01_decentralized_uploading中增加真实编辑器/后端存储浏览器验收，覆盖新增331/0.1→296/0.16、保存失败恢复与焦点/滚动，记录边界。
- [x] T007 [US3] 只读核查目标草稿，更新validation.md、上传Overview和Issue；仅提交本次增量，不推送。

顺序：T001→T002→T003→T004→T005→T006→T007；同文件串行。US1可独立以保存验证验收，US2以版本/证据对照验收，US3以浏览器及持久化验收。FR/SC覆盖见plan.md。

## 当前验收状态

T002～T005：后台已实施，独立HEAD增量112项相关回归、10项真实MySQL回滚测试通过。T006：用户单独授权前端定位/失效逻辑后，两处逻辑修复完成，61项前端回归与TypeScript检查通过；真实上传详情路由的10个浏览器检查点通过（包括删除组首点及保存后状态）。T007：当前真实草稿只读复核145项条件有效，保存校验及文档已完成；提交号在Issue追加。不推送，不关闭Issue；远程链接及部署边界见validation.md。
