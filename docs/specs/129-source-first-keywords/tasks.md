# 实施任务

**输入**：[规格](spec.md)、[计划](plan.md)、[契约](contracts/keywords.md)、[验收](quickstart.md)。Issue 状态由 [#129](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/129) 管理。

## 阶段 1：需求与基础

- [x] T001 建立 `docs/specs/129-source-first-keywords/` 的 Spec、Plan、Research、数据模型、接口、验收与需求检查表。（FR-001—007）

## 阶段 2：作者关键词（US1）

- [x] T002 [US1] 在 `backend/tests/test_keyword_extraction.py` 加入中英文作者列表、页码、参考文献与补充材料边界测试。（FR-001—003，SC-001/004）
- [x] T003 [US1] 在 `backend/ingest/keyword_extraction.py` 实现主文关键词栏识别、去噪、逐字定位与来源分析。（FR-001—003）

## 阶段 3：全文提炼（US2）

- [x] T004 [US2] 在 `backend/tests/test_keyword_extraction.py` 加入无列表短文、长文全部窗口、失败留空与依据校验测试。（FR-004/005，SC-002/004）
- [x] T005 [US2] 在 `backend/ingest/keyword_extraction.py` 实现全文窗口阅读、统一提炼和失败状态。（FR-004/005）
- [x] T006 [US2] 在 `backend/ingest/upload_jobs.py` 接入来源优先选择，停用只看标题摘要的缺失补齐；在 `backend/ingest/language_contract.py` 仅豁免有定位作者原词的中文关键词。（FR-002/004/005）

## 阶段 4：来源与校对（US3）

- [x] T007 [US3] 在 `backend/ingest/scientific_evidence.py`、`backend/ingest/property_evidence.py` 与上传草稿 API 接入当前值匹配的来源分析，防止人工改值复用旧证明。（FR-006/007，SC-003）
- [x] T008 [US3] 在 `frontend/src/components/EvidenceWorkflow.tsx` 及中英文文案中明确显示作者原列、AI 全文提炼和待核对状态。（FR-006，SC-003）

## 阶段 5：收敛

- [ ] T009 完成 `docs/specs/129-source-first-keywords/quickstart.md` 的定向与回归验证，回写对应 `docs/overview/` 并更新 #129 Documentation Impact。（SC-001—004）

**依赖**：T002→T003；T004→T005→T006；T003/T006→T007→T008→T009。T002 与 T004 可按文件编辑顺序串行执行。
