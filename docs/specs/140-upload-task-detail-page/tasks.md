# 实施任务：任务条框新标签页解析

输入：[Spec](spec.md)、[Plan](plan.md)、[Research](research.md)、[验收步骤](quickstart.md)。

## 准备与基础

- [x] T001 同步新标签页原话、需求结论及实施授权到 `spec.md` 和 GitHub #140，修正旧范围外事项。
- [x] T002 在 `frontend/src/pages/UploadTaskPage.tsx` 与 `frontend/src/LazyRoutes.tsx` 建立按账号及任务隔离的地址入口。

## US1：整条新标签页入口

- [x] T003 [US1] 在 `frontend/src/components/UploadTaskCenter.tsx` 将普通卡片区域设为新标签页链接，删除查看／收起按钮，补齐双语文案与键盘名称。
- [x] T004 [US1] 调整 `frontend/src/pages/UploadPage.tsx`，列表只保留上传和任务管理，不再恢复内联任务或在上传完成时展开。

## US2：任务详情与校对

- [x] T005 [US2] 在 `frontend/src/pages/UploadPage.tsx` 保留详情状态查询、重试、手填、核对和提交，改为地址任务与返回上传记录，处理失效与权限错误。
- [x] T006 [US2] 在 `frontend/src/components/UploadTaskEditor.tsx` 补足未保存／保存中表单的浏览器离页保护，复用原有草稿保存。

## US3：独立任务管理

- [x] T007 [US3] 在 `frontend/src/components/UploadTaskCenter.tsx` 保留独立多选、取消、清理和批量删除，重新获焦刷新列表；通过现有相关测试。

## 验证与收尾

- [x] T008 更新 `tests/01_decentralized_uploading/upload-task-workspace.test.tsx` 并新增详情地址与离页保护回归，覆盖 SC-001—005；运行相邻测试及前端构建。
- [x] T009 通过实际浏览器验证原上传页、新标签页详情、原页面保留及刷新恢复，并记录到本目录 `validation.md`。
- [x] T010 根据落地结果更新 Overview、根 `README.md`、需求检查表和 GitHub #140；精确分离原有工作区改动并检查提交范围，不推送。

## 依赖、覆盖与交付

T001 → T002 → T003—T007 → T008—T010。同一文件改动顺序执行，不并行代理工作。MVP 是任务条框新标签页打开且可完成原有校对流程；其余任务是回归和文档收尾，不新增独立功能。

| 来源 | 任务 |
| --- | --- |
| FR-001、002、008 / SC-001、003、005 | T002—T004、T008—T009 |
| FR-003、004、006 / SC-002、004 | T002、T005、T008—T009 |
| FR-005 / SC-003 | T003、T007—T009 |
| FR-007 / SC-002、005 | T005—T006、T008—T009 |
| Documentation Impact | T001、T010 |

各项完成依据见 [validation.md](validation.md)：工作区 79 项、独立增量副本 77 项与构建、正式组件浏览器验证及文档回写。远程链接检查仍未完成，Issue 不关闭。
