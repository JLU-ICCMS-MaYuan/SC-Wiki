# 实施任务：提升上传解析的 LLM 提炼质量

**输入**：[Spec](spec.md)。Issue 状态由 [#120](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/120) 管理。

## 阶段 1：程序归一化与核对口径（US1）

- [x] T001 `backend/db_helpers.py`：`parse_formula_composition` 支持括号分组与 Unicode 下标，拒绝不配对/空括号。（FR-001）
- [x] T002 `backend/ingest/upload_jobs.py`：`_formula_from_material` 只取唯一完整化学式；无法确定时原文保留为材料名，替代式元素数按组分统计。（FR-002）
- [x] T003 `backend/ingest/scientific_evidence.py`：与符号查表一致的空间群编号、晶系改为派生核对项。（FR-003）
- [x] T004 `backend/ingest/property_evidence.py`：核对来源排除参考文献、单批 120000 字符、每批 20 项；聚合只采用有定位证据的判断。（FR-004）

## 阶段 2：LLM 提取与提示词（US2）

- [x] T005 `backend/ingest/upload_jobs.py`：提取窗口合并至 12000 字符，页码取窗口起点。（FR-005）
- [x] T006 三处提示词补充解析乱码修正、材料命名、状态合并、等价表示与概括口径；分段缓存版本升为 9。（FR-006）
- [x] T007 `backend/rag/llm.py`：流式中途断开可重试，默认重试 2 次并退避。（FR-007）

## 阶段 3：验证

- [x] T008 新增 `tests/01_decentralized_uploading/test_issue120_extraction_quality.py`，更新 `tests/test_db_helpers.py`、`test_property_evidence.py` 中过时断言。
- [ ] T009 用户指定测试集 14 组论文，基线（HEAD `913ec1c`）与新代码同模型对比，记录到 [验证记录](validation.md)。（SC-001、SC-002）
- [ ] T010 Overview 回写已落地行为。
