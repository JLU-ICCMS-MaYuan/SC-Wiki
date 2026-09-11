# 技术任务

按顺序实施，Issue 是协作状态来源。基础服务完成后接入 US1/US2，US3 验证两条流程。

- [x] T001 核验全部需求、设计、接口、任务和验证映射，docs/specs/103-property-evidence-review/
- [x] T002 [US1] 建立定位、多证据与同键隔离回归，tests/01_decentralized_uploading/test_property_evidence.py
- [x] T003 [US1] 修复证据转换与落库，backend/ingest/scientific_drafts.py、backend/api/rag.py、frontend/src/lib/propertyModules.ts
- [x] T004 新增模型与迁移，backend/models.py、alembic/versions/
- [x] T005 [US1] 实现共享核对服务与后台接口，backend/ingest/property_evidence.py、backend/api/evidence.py
- [x] T006 [US1] 接入上传事务与锁，backend/api/rag.py
- [x] T007 [US2] 接入审核事务、人工历史与删除生命周期，goserver/handlers/paper_evidence.go
- [x] T008 [US3] 建立前端状态机回归，tests/01_decentralized_uploading/evidence-workflow.test.tsx
- [x] T009 [US1] [US2] [US3] 共享组件与三个入口，frontend/src/components/EvidenceWorkflow.tsx、UploadTaskEditor.tsx、frontend/src/pages/AdminPage.tsx、AdminPaperEditPage.tsx
- [x] T010 [US1] [US2] 真实 MySQL 与 #29 验证，tests/01_decentralized_uploading/test_property_evidence_mysql.py、goserver/handlers/paper_evidence_mysql_test.go
- [x] T011 [US3] 浏览器验收、针对性回归与构建，docs/specs/103-property-evidence-review/quickstart.md
- [x] T012 回写 Overview、Issue 并规范提交，docs/overview/

验收证据及运行方式见 [验证路径](quickstart.md)。当前功能说明从 [Overview](../../overview/README.md) 导航；Issue 保有协作状态，本文不作为发布状态副本。

- [x] T013 [US1] [US2] 去除手动选片段和编辑引句，自动复用找到的证据；重试真正重查未解决记录；同步可读提示、回归和真实页面验收，并回写文档与 Issue。[FR-009 / SC-004]
- [x] T014 [US3] 为后台核对提供真实批次计数、进度条、阶段与等待计时；验证排队、进行中、取消及完成，回写接口、验收与 Overview。[FR-010 / SC-005]
