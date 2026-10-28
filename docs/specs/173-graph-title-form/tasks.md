# 实施任务

输入：[spec.md](spec.md)、[plan.md](plan.md)、[research.md](research.md)、[data-model.md](data-model.md)、[UI 契约](contracts/ui.md)。

- [x] T001 完成确认记录与本目录实施文档，核对需求和职责映射。
- [x] T002 [US1] 在 `tests/01_decentralized_uploading/graph-title-form.test.tsx` 建立真实宿主回归，先确认缺控件时失败。
- [x] T003 [US1] 修改 `frontend/src/components/UploadTaskEditor.tsx`、`frontend/src/lib/paperProcessing.ts`、`frontend/src/i18n/zh/upload.ts`、`frontend/src/i18n/en/upload.ts`，补齐控件、类型与文案。
- [x] T004 [US1] 运行定向测试、类型构建、适用后端保存验证及 `tests/01_decentralized_uploading/graph-title-browser.mjs`，记录 `validation.md`。证据：23 项前端检查、3 项生产存储验证、双视口浏览器及构建通过；1 项既有摘要测试基线失败独立记录。
- [x] T005 回写上传表单与图谱标题 Overview、根 README；更新需求检查表及 Issue 实施状态，按本任务明确路径暂存与独立提交。远程链接未验证，Issue 不关闭。

执行顺序 T001 → T002 → T003 → T004 → T005；一个完整用户故事，无额外增量阶段。

覆盖：FR-001/002/007、SC-001 对应 T002–T004；FR-003/006、SC-002/004 对应 T002–T004；FR-004/005、SC-003 对应 T002–T004。T005 负责 Documentation Impact，不代表远程链接已经通过。
