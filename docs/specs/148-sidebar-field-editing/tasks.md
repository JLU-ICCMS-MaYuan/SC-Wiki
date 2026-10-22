# 实施任务

输入：[Spec](spec.md)、[Plan](plan.md)、[调查](research.md)、[数据](data-model.md)、[契约](contracts/field-settings.md)。当前为设计草案，技术任务未实施。

- [x] T001 建立新 Issue，保留用户原话和澄清；调查 #103、#94、#109、#147 及当前代码，归档两张截图。
- [ ] T002 [US1] 在 tests/01_decentralized_uploading 增加真实 UploadTaskEditor／管理员论文字段设置复现，覆盖研究方法多行列表和原始编辑文本。
- [ ] T003 [US1] 在 frontend/src/components/UploadTaskEditor.tsx、frontend/src/pages/AdminPaperEditPage.tsx 接入共享论文文本／列表设置适配器及现有配置事件。
- [ ] T004 [US2] 在 frontend/src/components/ReviewFieldSettings.tsx、EvidenceWorkflow.tsx 去除两个重复返回入口，保留 × 和三个页签，未适配复杂字段至少可读显示名称和值。
- [ ] T005 [US1,US3] 覆盖标题、摘要、总结、主要发现、研究动机、关键词、研究方法，以及既有 Tc／μ*／计算条件设置；确认应用、取消、只读、换行、并发和切页签。
- [ ] T006 [US2,US3] 运行浏览器生产路由隔离验证：设置编辑不退出侧栏，单字段保存差异正确，零额外模型请求，窄屏无溢出。
- [ ] T007 验证通过后更新 Overview 审核部分及必要导航、README 与本 Spec 验收记录；仅本轮文件本地提交，不推送。

依赖：T001 → T002 → T003 → T004 → T005/T006 → T007。FR-001/002/005/008 由 T002/003/005 验证；FR-003/004 由 T004/005/006 验证；FR-006/007 由 T005/006 验证。复选框只有业务路径和对应验证通过后才能勾选。
