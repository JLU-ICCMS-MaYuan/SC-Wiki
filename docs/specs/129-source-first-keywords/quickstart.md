# 验收步骤

1. 运行 `pytest backend/tests/test_keyword_extraction.py backend/tests/test_upload_jobs.py`，确认作者列表、中文、长文、失败和定位场景通过。
2. 上传含“关键词：”的中文学位论文或夹具，以及含 `Keywords:` 的英文期刊论文；校对页应保留作者原词、顺序、文件、页码与引句。
3. 上传无关键词栏的期刊论文；检查全部有效正文窗口已参与，侧栏标明 AI 全文提炼，词项有当前论文依据。
4. 手工修改关键词并保存、刷新；旧作者列表或 AI 分析不能再被显示为当前值的直接出处。
5. 使用包含参考文献关键词、补充材料关键词及模型失败的夹具，确认不伪造作者列表或已完成全文提炼。

验证结果记录到本文件末尾；未实际运行的步骤保持未完成。

## 2026-10-11 自动化验证记录

- `backend/tests/test_keyword_extraction.py`：9 项通过，包括真实 PyMuPDF 文本层 → Markdown → 任务来源 → 作者关键词定位、中文原词、补充材料排除、长文全窗口、失败留空、人工改值旧证据失效和局部建议不得自动填词。
- `tests/01_decentralized_uploading/test_property_evidence.py`、`test_issue120_extraction_quality.py`、`backend/tests/test_narrative_english_output.py` 与关键词测试合计 37 项通过。
- 关键词侧栏两类来源文案 2 项、上传关键词编辑相关 2 项通过；`frontend/tsconfig.json` 类型检查通过。
- 整体回归有其他工作区改动引发的失败：`backend/tests/test_upload_jobs.py` 的旧材料归一化与理论子类型提示词断言共 2 项；上传布局文案断言 1 项命中其他任务新增的“全文 AI 建议”；条件测试夹具缺少 `user_id`。这些失败未作为本 Feature 的通过证据。
- 尚未对截图对应的 H3S 原 PDF 或真实学位论文运行模型及浏览器全流程；因此 T009 保持待验收，Issue 不关闭。

## 仅含 #129 变更的暂存版本验证

- 从 Git 暂存区导出独立副本，运行 `backend/tests/test_keyword_extraction.py` 与 `backend/tests/test_upload_jobs.py`：62 项通过；排除 1 项 `test_normalize_legacy_li2mgh16_properties_into_scientific_material_state`，该项在未纳入本 Feature 的既有归一化代码下失败。
- 独立副本中的 `evidence-workflow.test.tsx` 与 `upload-task-editor-layout.test.tsx`：55 项通过；`frontend/tsconfig.json` 类型检查通过。
- 此验证只证明暂存代码与组件行为，不表示运行服务已部署或真实论文模型输出已验收。

## AI 选择理由增量验收

1. 作者原列关键词仍显示原文来源；无作者列表时让模型通读代表论文，检查 `keyword_assessment.reason` 对所选材料、现象、方法词有具体解释，而非只写“已通读全文”。
2. 分别注入空理由、过程性泛泛理由、引句失败和人工改词，确认当前侧栏待重核，旧理由只留历史；模型不能把作者原列词冒充自身推断。
3. 上传、刷新、转论文和管理员重读同一词列表时，核对理由与来源版本一致，其他字段和关键词优先级不回归。

本轮作者原列与全文提炼分支的定向回归通过；全文关键词真实模型只读调用返回材料、现象和方法的选词理由，同时指出代表引句的局限。模型结果未写回 H3S 草稿。正式转接和管理员重读尚未验收，T013 保持未完成；测试结果与边界见 [#109 验收记录](../109-field-evidence-and-ai-suggestions/quickstart.md#本轮实测)。
