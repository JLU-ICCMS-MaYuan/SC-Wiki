# 实施任务：领域提取覆盖全部表格行/结果块/图

**输入**：[Spec](spec.md)。Issue 状态由 [#122](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/122) 管理。

## 阶段 1：契约与提示词

- [x] T001 `backend/ingest/domain_extraction.py`：`Extraction` 新增 `coverage_exclusions`（`CoverageExclusion` 模型：file_id + block/table row/page 定位 + 受控 category + reason）；`DOMAIN_SYSTEM_PROMPT` 要求候选与排除必居其一。（FR-001、FR-002）
- [x] T002 `normalize_extraction`：校验排除项引用的块/表行/页真实存在（对 allowed_blocks 与 IR 表格结构），无效排除项丢弃且不改变未覆盖语义。（FR-003）

## 阶段 2：覆盖检查

- [x] T003 `backend/ingest/coverage_audit.py`：`audit_coverage` 接收排除项；被排除项移出 `uncovered_candidates`；`unreadable` 类别与排除比例超阈值（50% 疑似结果块+表格行）保持 `requires_human=True`；`CoverageReport` 新增 `exclusions` 字段并写入 coverage.json。（FR-004、FR-005）
- [x] T004 `backend/ingest/upload_jobs.py`：把领域提取的排除项传入 Claim 组装与覆盖检查；`repair_claims` 循环不变。（FR-006）

## 阶段 3：验证

- [x] T005 新增单元测试：排除契约校验、无效引用丢弃、类别阈值与 requires_human 语义、coverage.json 记录。
- [x] T006 2014 H3S 主文 + 补充材料 Docling 完整管线实测（复用 IR 缓存重跑 reading 之后的阶段），达到 ready 或 requires_human 项全部明确列出；#114 定向测试无新增失败。（SC-001、SC-002）
  - 实测结果（2026-10-09）：补充材料覆盖检查 `complete`（45 行晶格/坐标表按 out_of_model_scope 诚实标注，0 未覆盖）；主文仅剩 1 项需提取的谱函数段落在失败信息与 coverage.json 中明确列出（SC-001 第二分支）；46+56 项排除全部带类别与理由（SC-002）。相关测试 58 passed 8 skipped。
- [x] T007 Overview 回写：pdf-parsing-pipeline.md 覆盖检查段落更新排除机制。
