# 实施任务

Issue 为协作状态唯一来源。本文件记录技术拆解。

## 基础与 US1

- [x] T001 [US1] 在 `tests/01_decentralized_uploading/scientific-evidence-markers.test.tsx` 和证据工作流测试新增全字段、空态、解决后入口及顶部列表移除的失败用例。
- [x] T002 [US2] 在 `tests/01_decentralized_uploading/test_field_suggestions.py` 新增字段目录、依据分类、生成/复核、采用与门禁失败用例。
- [x] T003 [US2] 扩展 `backend/ingest/scientific_evidence.py`、`evidence_proposals.py`、`property_evidence.py` 的空字段、建议与采用版本契约。
- [x] T004 [US1] 更新 `frontend/src/components/EvidenceFieldMarkers.tsx`、`EvidenceWorkflow.tsx` 及两个编辑入口和共用字段组件，补齐字段点击与三类结果侧栏。

## US2 与 US3

- [x] T005 [US2] 接入 `backend/ingest/upload_jobs.py` 上传建议生成及 `backend/api/evidence.py` 全量审核任务目的，验证取消、进度和失败恢复。
- [x] T006 [US3] 更新 `goserver/handlers/paper_evidence.go` 和 `backend/rag/scientific_sources.py` 的永久归档及推测归因，补齐跨层批准验证。

## 验收与交付

- [x] T007 [US3] 在真实存储回滚/隔离夹具中验证上传转论文、批准重读、空项保留、推测门禁及来源失效；记录到 `quickstart.md`。
- [x] T008 [US1] 完成桌面/窄屏、三入口、键盘、滚动及多状态浏览器验证，执行相关前后端测试与构建。
- [x] T009 [US2] 执行受控真实模型生成与复核，单独记录服务配置可用性、输出及局限，不修改真实科学记录。
- [x] T010 更新对应 `docs/overview/` 与 `README.md`、复核需求覆盖、独立审查修复、仅提交本任务差量，回写并按验收关闭 Issue。

顺序：T001/T002 → T003 → T004/T005 → T006 → T007/T008/T009 → T010。共享文件串行处理；每个故事须具备实际存储或浏览器信号后才标记完成。
