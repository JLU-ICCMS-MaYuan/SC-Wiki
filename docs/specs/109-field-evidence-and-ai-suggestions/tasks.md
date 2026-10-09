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

## 2026-10-09 追加阶段：可核验的支持结论（US4，未实施）

旧 T001—T010 的完成状态只对应原验收；下列任务用于 FR-010—014 / SC-006—008。

- [ ] T011 [US4] 在 `tests/01_decentralized_uploading/test_property_evidence.py` 和定向真实来源测试中复现概括字段无引句仍显示 `supported`、事实引句不相关及派生输入失效，先锁定来源资格与版本边界。
- [ ] T012 [US4] 更新 `backend/ingest/property_evidence.py`、`backend/ingest/scientific_evidence.py` 与必要的来源契约：统一当前值的支持资格、定位失败状态、派生输入和规则版本；保留旧结果只读历史，不批量改写论文。
- [ ] T013 [US4] 在 `tests/01_decentralized_uploading/evidence-workflow.test.tsx` 与 `field-evidence-browser.mjs` 增加首屏可见引句、无替换建议仍显示依据、无来源提示及三入口鼠标/键盘用例。
- [ ] T014 [US4] 更新 `frontend/src/components/EvidenceWorkflow.tsx`、`EvidenceRegion.tsx` 及中英文字典：区分当前结论、AI 理由、原文/派生依据和替换建议，首屏显示第一条来源，图片加载失败仍保留引句。
- [ ] T015 [US4] 按 `quickstart.md` 的新增验证路径，使用真实持久化和可复现 H3S 来源夹具核对上传→待审→批准重读、同名跨文件引句、概括多论断、旧版本和无来源状态；记录通过信号与未满足项。
- [ ] T016 [US4] 完成需求收敛和文档影响检查；使用 `big-project-overview-maintainer` 回写已实现行为，更新 `README.md` 的查看方法，并在 SC-006—008 全部满足后按 Issue 管理流程收尾 #109。

执行顺序：T011 → T012，T013 → T014，随后 T015 → T016；后端与前端实现可分别推进，但共同验收和 Issue 收尾必须串行。

## 2026-10-09 追加阶段：人类可读的侧栏与人工证据（US5，未实施）

以下任务对应 FR-015—021 / SC-009—012；旧任务的勾选不能证明本阶段完成。

- [ ] T017 [US5] 在 `tests/01_decentralized_uploading/evidence-workflow.test.tsx`、`scientific-evidence-markers.test.tsx` 和浏览器夹具中先复现作者 JSON、原文折叠、图像证据不可见及建议区命名问题，锁定桌面/窄屏/键盘验收。
- [ ] T018 [US5] 在 `tests/01_decentralized_uploading/test_scientific_evidence_mysql.py` 与新增人工证据用例中先覆盖修改识别、有/无证据时的理由门禁、值版本失效、文件权限、回滚与任务清理。
- [ ] T019 [US5] 为 `backend/models.py` 和 Alembic 新增 `scientific_manual_evidence` 迁移与私有文件存储；在 `backend/api/evidence.py` 实现文字/截图/TXT/MD 的保存、鉴权预览、类型与哈希校验及待提交删除。
- [ ] T020 [US5] 在 `backend/api/rag.py`、`backend/services/paper_revisions.py` 和 `goserver/handlers/paper_evidence.go` 实现上传、返修及批准时的人工证据版本绑定与永久归档，验证失败恢复及不混入 `paper_files` 原论文语料。
- [ ] T021 [US5] 更新 `frontend/src/components/EvidenceWorkflow.tsx`、`EvidenceRegion.tsx` 与中英文字典：移除“当前内容”JSON，系统原文默认展开并可折叠，人工修改区显示可读差异、理由和证据，建议区更名并保持类型化编辑。
- [ ] T022 [US5] 更新 `backend/ingest/property_evidence.py` 与审核 AI 输入适配：人工文字和图片带 `human_provided` 来源独立输入，记录是否实际读取；模型无图像能力或读取失败时不假称已核验，并加入提示注入隔离测试。
- [ ] T023 [US5] 在上传、返修和管理员正式提交门禁中按服务端规范值逐字段检查人工修改理由及无证据原因；保留自动保存半成品、改回原值豁免与按字段定位的错误反馈。
- [ ] T024 [US5] 使用真实 MySQL 回滚事务、私有文件存储、审核 AI 图像路径和实际浏览器验证 SC-009—012，包括刷新、越权、重复提交、历史版本、图像失败及移动端，记录到 `quickstart.md`。
- [ ] T025 [US5] 复核 FR/SC/任务覆盖与文档影响；实际实现并验收后使用 `big-project-overview-maintainer` 更新 Overview、补充 `README.md`，再按 Issue 管理流程关闭 #109。

2026-10-09 实施记录：T011—T023 的主要代码路径及定向测试已写入；Overview 与 README 已同步可由代码及隔离测试证实的行为。无头 Chrome 的三入口隔离夹具已通过；真实业务 MySQL 的完整上传→返修→批准事务、真实 H3S 来源页面及可处理图片模型仍待验收，因此相关任务复选框和 T024—T025 均不提前标为完成。验证结果与环境限制见 [quickstart.md](quickstart.md)。

顺序：T017/T018 → T019/T023 → T020/T021/T022 → T024 → T025；T011—T016 的来源资格与首屏证据约束须在最终验收前完成。共享保存与审核边界串行处理。
