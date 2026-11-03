# 实施任务：用户指定上传文件身份

**输入**：[Spec](spec.md)、[Plan](plan.md)、[Research](research.md)、[数据模型](data-model.md)、[契约](contracts/upload-files.md)。

## 阶段一：文档与质量门

- [x] T001 确认 spec.md 原始需求与本次“开始 实现”，建立本目录设计、接口和 FR/SC 映射，保留远程链接未完成。

## 阶段二：US1 上传入口与清单

- [x] T002 [US1] 在 tests/01_decentralized_uploading/manual-upload-files.test.tsx 和 test_manual_upload_roles.py 先验证新数量/错区/三入口场景能失败。
- [x] T003 [US1] 修改 frontend/src/components/MultiFileUploadPanel.tsx 和 frontend/src/i18n/{zh,en}/upload.ts，三区域共用稳定清单和队列，保留原选择与错误。
- [x] T004 [US1] 在 backend/ingest/upload_contracts.py 统一数量与角色格式校验；更新受影响旧夹具以表达 supplementary 文本。

## 阶段三：US2 指定角色直接生效

- [x] T005 [US2] 在 backend/ingest/upload_tasks.py 创建服务器策略标记，backend/ingest/upload_jobs.py 按标记跳过角色判断；保留无标记历史恢复和真实一致性检查。
- [x] T006 [US2] 在 tests/01_decentralized_uploading/test_manual_upload_roles.py 验证误导文件名、多份论文式文本、纠正文稿和弱正文均进入指定来源，无角色评估调用；运行旧角色 API 和恢复回归。

## 阶段四：US3 来源与结构能力

- [x] T007 [US3] 覆盖多补充材料/纠正文稿科学来源、原生结构的真实解析和来源保留；运行结构/保存重读/事务/队列/identity 回归，在隔离副本记录实际 PDF 或模型验证及未完成边界。

## 阶段五：集成和收尾

- [x] T008 运行 tests/01_decentralized_uploading/manual-upload-files-browser.mjs 完整 UploadPage 桌面/390px 交互，记录 API 隔离与真实表现。
- [x] T009 运行两项表单契约、影响回归和前端构建；更新 README.md、上传 Overview、#174 form-inventory.md 与本目录 validation.md；确认自身改动范围并自动提交，Issue 留 open 等待远程链接及剩余验收。

## 依赖与覆盖

T001 → T002 → T003/T004 → T005 → T006/T007 → T008/T009。全部故事为 P1，完整交付为本次范围；同文件变更串行。FR-001—003/SC-001 对应 T002—004；FR-006—007/SC-002、005 对应 T005—006；FR-004—005、008/SC-003—004 对应 T007；FR-009—011/SC-006 对应 T005—007；FR-012/SC-007 对应 T008—009。

## 实施与验证结果

本轮技术任务已执行，实际证据与旧失败基线见 [validation.md](validation.md)。T007 的保存重读为隔离文件链路，历史业务数据库扩展测试有同基线的既有失败，不声明全部落库验收通过；T009 的远程链接/CI/部署不在本轮授权范围，Issue 保持开放。

## 2026-11-03 既有逻辑补齐

- [x] T010 [US1] 针对 H3S 黑盒发现的重复文件 500，在 `tests/TestForRealScenario/verify_upload_conflict.py` 先复现失败，再补齐上传 PUT 的 409 错误转换；验证本地及对象存储只清理被拒副本、原件保留、同任务补传恢复及只入队一次。影响回归与独立 HEAD 的相同三项既有失败见 validation.md；真实 H3S 全流程尚未验收。
