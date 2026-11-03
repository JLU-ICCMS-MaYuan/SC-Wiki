# 实现回溯：CaH6解析回归修复

**Issue**：[＃208](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/208)。**日期**：2026-11-03。**Spec**：[spec.md](spec.md)。

本文件记录`b1fc93be`已经采用的办法，不是新一轮待实施方案。实现理由见[research.md](research.md)，验收见[validation.md](validation.md)。

## 技术上下文

- Python 3.12后端、React/TypeScript前端；已有FastAPI、SQLAlchemy、MySQL、Redis/RQ、pymatgen/spglib及JSON Schema校验库。
- 本机原生环境，Vite 5173、MySQL 127.0.0.1:3307/scwiki；原文件与制品使用既有存储抽象。
- 本次业务源码只修改后端14个文件；前端通过实际页面及四类宿主回归验收。
- 不改数据库表结构、不增加标准键；不新增性能指标。保留#174局部更新、稳定身份和输入/保存/审核分离要求。

## 数据所有权与模块关系

解析模块负责候选和原文；模型决定科学含义与归属；程序检查类型、身份、权限及保存。页面摘要读取同一当前版本，主表单与独立谱任务分别显示状态。永久结构承接原子文件与派生表示，临时模型输入不进入交接快照或逐字段持久结果。

## 需求到设计和证据的映射

| 来源 | 实施触点 | 实际处理与证据 |
| --- | --- | --- |
| FR-001 / US1 | `backend/ingest/scientific_form_filling.py` | 先检查科学字段再添加服务器分组、历史标签；`test_scientific_form_filling.py`及真实最终同组两点 |
| FR-002 / US1 | `backend/ingest/model_review.py::_add_conditions` | 仅初始化合法空根和软件组；`test_unified_model_review.py` |
| FR-003 / US1 | `backend/ingest/upload_jobs.py::complete_parsing_state` | 错误保留failed及预览，成功才ready；`test_parsing_preview_sync.py` |
| FR-004 / US3 | `backend/ingest/scientific_evidence.py::delete_target` | 删除upload工作稿和来源使用关系；`test_upload_workdraft_cleanup.py`及真实旧稿清理 |
| FR-005 / US2 | `backend/ingest/structure_extractor.py` | 三列晶胞表、符号与菱方设置进入既有严格验证；`backend/tests/test_structure_extractor.py`及真实11结构 |
| FR-006 / US2 | `material_state_contract.py`、`canonical_structure.py` | 归属前统一补身份，保留非空编号并拒绝重复；`test_parsing_state_identity.py`及结构归属回归 |
| FR-007 / US1、US2 | `evidence_proposals.py`、`property_field_review.py` | 复用已登记JSON Schema，保留有限数值、长度、枚举和未知键限制；`test_registered_review_types.py` |
| FR-008 / US3 | `model_review.py::review_fields` | 候选差异比较复用科学数值规范化；同值固定失败回放 |
| FR-009 / US2 | `scientific_evidence.py`、`model_review.py`、`property_evidence.py`、`services/manuscript_handoffs.py` | 临时传完整结构并在公开、保存、交接处剥离；`test_structure_review_input.py` |
| FR-010 / US2 | `material_state_contract.py::research_materials`、`model_review.py`、`api/rag.py`、`evidence_proposals.py` | 复用旧汇总算法，当前卡片产生只读材料汇总；统一核对回归与真实最终列表 |
| FR-011 / US2 | `backend/api/evidence.py::field_summary` | 轻量摘要复用apply_derived；MySQL结构派生回归及实际页面0红框 |
| FR-012 / US3 | 同上 | 对投影小行在程序中排序，不改变当前版本优先；真实大型表单提交后读取通过 |
| FR-013 / US3 | `backend/services/spectra.py::context` | 首次创建后重读持久body再计算版本；`test_spectrum_initial_workdraft_mysql.py`及真实谱发现任务结束 |

上表未写全路径的后端模块均位于`backend/ingest/`；未写全路径的`test_*.py`均位于`tests/01_decentralized_uploading/`。这是路径缩写说明，不新增模块。

## 阶段与依赖

1. 只读索引全仓，精读命中的旧Issue/Spec和完整受影响调用链；不把检索说成逐行理解全部代码。
2. 保存失败材料，先证明回归能检出，再修复类型、分组、身份和完成状态。
3. 补结构表读取、完整结构审核输入及当前材料汇总；联查页面摘要、保存和清理入口。
4. 全部业务修改完成后删除备份过的旧稿，重新HTTP上传两份PDF；运行期间冻结后端源码。
5. 等自动核对结束，实际浏览器检查，再完整提交/两角色批准/重读外层回滚验证；独立谱如实记录限制。
6. 补建#208文档、检查相对链接和需求覆盖，本地仅提交本次记录；远程链接待验证。

## 质量门与必要复杂度

| 约束来源 | 如何满足 | 结果 |
| --- | --- | --- |
| #203/#205固定字段 | 未改权威JSON及锁，类型复用已有契约 | 既有字段检查通过 |
| #174表单 | 四类宿主132项通过，8项变异检出 | 保留原范围，未宣称全站所有表单通过 |
| #183/#194来源与复用 | 当前值、依据和派生结果统一；程序不重做科学裁决 | 页面和隔离完整提交通过 |
| PDF源头重跑 | 最终从原PDF重新上传和重新模型提取 | 不是旧稿回放冒充整篇重跑 |
| 旧测试失败 | 独立归档`bdb81d6f`逐项对比 | 单列旧失败与跳过 |
| 文档发布 | 不自行推送、不用本地路径冒充远程URL | Issue保持开放 |

额外复杂度限于缺失的表格读取、临时结构输入和持久版本重读。没有新增审核状态体系或永久第二份科学事实；不采用删除白名单、调大数据库全局内存、统一四舍五入指纹或伪造人工通过的捷径。
