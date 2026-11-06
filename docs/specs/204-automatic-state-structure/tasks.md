# 技术任务

- [x] T001 创建#204与完整需求/方案/数据契约，依赖#203且无父子关系；保留原图。证据：spec.md及assets。
- [x] T002 模型联合原文归属并检查材料组成、压力、几何与优化类型；保护已有人工结构。证据：backend/tests/test_canonical_structure_assignment.py和verification/structure-live-report.json。
- [x] T003 正式草稿仅S.structure，承接来源/校验/派生表示；上传、返修、管理员、查看、保存重读和导出接通。证据：verification/formal-roundtrip-report.json。
- [x] T004 完整伴随结构可独立建卡、同压不同优化不混写，旧失败记录不会把人工替换后的新结构直接标成旧失败。证据：结构回归与两次真实失败响应。 科学字段右侧栏功能设计、原话及历史已迁移至 [#221](../221-scientific-field-sidebar/spec.md)，本处不再独立维护。
- [x] T005 增量metadata列及当前工作稿转换，冻结历史/原始资料保留；最终源码用真实备份再恢复重放。证据：verification/migration-report.json及final-source-replay-report.json。
- [x] T006 完整四宿主132项、变异8项、类型/构建、后端及正式MySQL提交/新会话重读通过；旧失败和未验收范围单列。证据：validation.md。
- [x] T007 以本次#204提交记录证明精确增量，更新Issue；Overview/README和本机启动清单已同步，未推送Spec不得关闭Issue。
- [ ] T008 用户旧页面缺失字段现场与完整HTTP/RQ整篇成功验收；不把定向字段验证等同于整篇解析恢复。

- [ ] T009 两个Issue的远程Spec链接实际可访问；未推送，保留开放和待核验，不为收尾擅自推送。

- [x] T010 原SI正式入口只读重放确认0候选，实际上传接线回归先失败；证据见TestForRealScenario本轮structure-content-before.txt及fourth-structure-extraction-replay.json。
- [x] T011 接通PDF内容识别、严格内部描述与原来源/几何校验，保留旧调用；字段契约不变。 科学字段右侧栏功能设计、原话及历史已迁移至 [#221](../221-scientific-field-sidebar/spec.md)，本处不再独立维护。
- [ ] T012 用原PDF新AI读取并走后处理/归属/隔离保存重读，覆盖共享回归和字段/表单/变异；第五轮网页全新上传及五阶段验收。

- [ ] T013 第七轮结构原页双计费/回执丢失反例先失败，修复后从原PDF真实模型读取、正式归属/隔离往返、字段/表单/变异与真实新上传验收；不扩大12次行动上限。

- [x] T014 以LaBeH8真实响应先检出原符号误拒绝及独立位点未展开，适配原行到既有解码；隔离45项回归、字段契约、198项四宿主及12项变异检查通过，原PDF新模型读取恢复8份完整模型。证据见validation.md本轮记录。
- [ ] T015 完成LaBeH8修复后的相同原PDF新上传、送审、退回、返修、批准及本轮论文检索；保持原模型，重复请求修复已完成专项验证，须重新进行网页验收；结构专项不代表整篇解析或业务流程完成。

- [x] T016 固定真实SI结构call-4失败请求对照，新增2项回归先失败，修复后47项结构回归、字段契约、198项四宿主及12项变异通过。原SI新AI完整读取5调用通过，8份结构经真实归属、隔离正式保存/新会话重读相等；详见validation.md。整篇网页仍由T015验收。
