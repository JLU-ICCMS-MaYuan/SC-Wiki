# 实施任务：浅度论文解析

输入：[Spec](spec.md)、[Plan](plan.md)、[Research](research.md)、[数据模型](data-model.md)、[接口契约](contracts/upload-and-search.md)。

## 准备与基础

- [x] T001 核对已确认 Spec、既有 Issue/Overview；记录原五个修改文件，保护原工作区。
- [x] T002 [US1] 在 tests/01_decentralized_uploading/test_shallow_parsing.py 和 shallow-parsing.test.tsx 建立模式及零科学调用失败测试。
- [x] T003 [US1] 修改 backend/api/upload_tasks.py、backend/ingest/upload_tasks.py、upload_contracts.py，实现延后入队及原子模式选择。
- [x] T004 [US1] 上传完成后在 frontend/src/pages/UploadPage.tsx 提供可恢复模式选择；MultiFileUploadPanel.tsx 发起延后任务。

## 浅度提取与提交

- [x] T005 [US2] 在 backend/ingest/shallow_parsing.py 注册并实现独立论文级提取；upload_jobs.py 分派后不进入科学和核对路径。
- [x] T006 [US2] 修改 UploadTaskEditor.tsx，实现论文级输入、保存与直接提交，零核对请求；深度保持原宿主。
- [x] T007 [US2] 在 backend/api/rag.py 复用正式提交事务并加入浅度服务器校验、published 状态及原文件/作者角色/分类保存；先写提交失败及绕过防护测试。
- [x] T008 [US2] 更新 backend/models.py 状态约束及对应 Alembic 迁移；在隔离实例验证约束及重读，不执行业务迁移。

## 搜索、深度回归与收尾

- [x] T009 [US3] 在 goserver/handlers/search_results_test.go 建立无状态论文、科学条件排除、公开权限、分页及去重失败测试。
- [x] T010 [US3] 修改 Go 论文查询及详情，增加浅度论文匹配；前端搜索提供标题／DOI入口及“直接收录”展示。
- [x] T011 [US4] 执行字段契约、表单契约、变异、相关 Python/Go/前端回归及生产构建；失败如实隔离或修复。
- [x] T012 [US1—US4] 从真实来源执行论文级模型提取、正式后续处理和隔离入库/重读/搜索；保存模型、源码、来源与零科学/核对调用证据。
- [x] T013 按实际结果更新本目录验收、README、表单清单及受影响 Overview；核对本次暂存范围后自动提交，保留远程链接待验证。

## 执行依赖与覆盖

T001→T002→T003/T004→T005/T006→T007/T008→T009/T010→T011/T012→T013。共享文件串行，不启用子代理。
FR-001 对应 T002—004；FR-002—006 对应 T005—008/T012；FR-007—008 对应 T009—010/T012；FR-009—010 对应 T003/T007/T011。SC-001—006 的证据写入 validation.md，测试通过后才勾选实现项。
