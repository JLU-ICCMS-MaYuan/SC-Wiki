# 技术任务

- [x] T001 创建#204与完整需求/方案/数据契约，依赖#203且无父子关系；保留原图。证据：spec.md及assets。
- [x] T002 模型联合原文归属并检查材料组成、压力、几何与优化类型；保护已有人工结构。证据：backend/tests/test_canonical_structure_assignment.py和verification/structure-live-report.json。
- [x] T003 正式草稿仅S.structure，承接来源/校验/派生表示；上传、返修、管理员、查看、保存重读和导出接通。证据：verification/formal-roundtrip-report.json。
- [x] T004 结构问题通过字段侧栏/既有兜底可达；完整伴随结构可独立建卡、同压不同优化不混写，旧失败记录不会把人工替换后的新结构直接标成旧失败。证据：结构回归与两次真实失败响应。
- [x] T005 增量metadata列及当前工作稿转换，冻结历史/原始资料保留；最终源码用真实备份再恢复重放。证据：verification/migration-report.json及final-source-replay-report.json。
- [x] T006 完整四宿主132项、变异8项、类型/构建、后端及正式MySQL提交/新会话重读通过；旧失败和未验收范围单列。证据：validation.md。
- [x] T007 以本次#204提交记录证明精确增量，更新Issue；Overview/README和本机启动清单已同步，未推送Spec不得关闭Issue。
- [ ] T008 用户旧页面缺失字段现场与完整HTTP/RQ整篇成功验收；不把定向字段验证等同于整篇解析恢复。

- [ ] T009 两个Issue的远程Spec链接实际可访问；未推送，保留开放和待核验，不为收尾擅自推送。
