# 实施任务：四工具互补 PDF 解析

输入：[Spec](spec.md)、[Plan](plan.md)、[Research](research.md)、[数据模型](data-model.md)、[接口契约](contracts/demo.md)。

## 准备与基础能力

- [x] T001 确认 Spec 并记录实际引擎环境与下游模型配置，在 `docs/specs/136-complementary-pdf-parsing/research.md` 和 `scripts/complementary_pdf_demo/requirements-marker.txt` 固定运行依据。证据：validation 的实际版本、模型摘要及相同提示哈希，另有完整 requirements-marker-lock.txt。
- [x] T002 实现 `scripts/complementary_pdf_demo/run.py` 和 `cases/h3s-2014.json`，校验输入、隔离唯一运行目录、保留原始结果及运行基线。证据：主运行 manifest、失败尝试归档及输入哈希/进程失败测试。

## US1：三路真实结果（P1）

- [x] T003 [US1] 在 `scripts/complementary_pdf_demo/parsers.py` 实现三路隔离执行、原始输出留存和 Marker 到 IR 的转换，实际解析两份 PDF 验证页面与来源。证据：validation 六次成功解析、原始 JSON/IR 与页数/摘要；坐标和表格边界测试通过。
- [x] T005 [US1] 在 `scripts/complementary_pdf_demo/extraction.py` 共用当前领域与表单契约，实现四臂相同模型/提示/预算、来源验证、结构候选及错误留存。证据：最终四路真实 call.json 和 form.json，完整表单不兼容项及引句失败均保留；不表示候选已可生产提交。

## US2：互补和核对（P1）

- [x] T004 [US2] 在 `scripts/complementary_pdf_demo/complement.py` 实现内容触发、区域对齐、候选取用与差异保留，在 `tests/test_demo.py` 验证跨页/跨文件、一对多及缺坐标边界。证据：真实 routing.json 的 192 组及 14 项测试；科学效果退步另见收敛任务，不能据此切生产。
- [x] T006 [US2] 在 `scripts/complementary_pdf_demo/report.py` 和 `template.html` 实现四路表单、完整字段、来源/覆盖、核对保存及导入导出，在浏览器验证真实报告。证据：validation 中的区域高亮、mu_star 筛选、JSON 导出/导入往返、跨运行拒绝；自动文件下载仍有浏览器限制，提供可复制完整 JSON。
- [x] T007 [US2] 实际执行 H3S 六次解析与四路提取，在 `docs/specs/136-complementary-pdf-parsing/validation.md` 记录准确度检查的分母、改善、退步、失败与未决项，不能用 Mock 代替。证据：34 项生成后参考、evaluation.json；Docling/Marker 34、MinerU 32、互补 28 项匹配，明确记录互补退步。

## US3：通用入口与后续生产（P2）

- [x] T008 [US3] 更换输入清单验证通用入口，并完善 `docs/specs/136-complementary-pdf-parsing/quickstart.md` 和验证证据；只提交本任务脚本与文档。证据：calcium-hydride-smoke 三次真实解析及 HTML，未宣称第二论文科学质量已验收。
- [x] T009 [US3] 2026-10-14 用户确认四工具架构并授权正式实现，唯一默认及 Overview 已由 T016–T021 完成；证据见 validation 正式工作流、API/UI 与提交源码测试。该状态不把旧三引擎负面实验称为验收成功。

## 依赖与验收

T001 → T002 → T003 → T004 → T005 → T006 → T007 → T008；T009 依赖用户验收真实 demo。编号用于稳定追踪，不表示展示顺序；同一文件修改串行。MVP 是可核对的真实四路报告，不以框架空壳作为完成。

需求映射见 Plan 完整表。US1 独立验收为六份真实原始结果和统一模型的表单/契约报告；US2 为真实 HTML 中来源、差异、遗漏和核对恢复；US3 当前只验收换输入，生产保持未完成。文档远程链接和背景图缺口独立保留，不据此宣布 Issue 完成。

## 阶段 6：真实 demo 后的收敛

- [ ] T010 [US2] 改进 `scripts/complementary_pdf_demo/complement.py` 的内容取用粒度及 `extraction.py` 的压力归属约束，以新运行验证互补不会把不同压力合并；来源 FR-005/FR-006/FR-007，差距类型 partial。当前实现可审计但科学效果退步，不能把 T004 视为准确度验收。
- [ ] T011 [US1] 在 `scripts/complementary_pdf_demo/extraction.py` 明确全部论文枚举及范围参数的表单承接，保持与 #120 的当前契约一致；来源 FR-008/SC-002，差距类型 partial。当前保留并标出不兼容候选，尚未达到可提交完整表单。
- [ ] T012 完成本版 demo 用户验收及文档收尾，在 `docs/specs/136-complementary-pdf-parsing/checklists/requirements.md` 继续核验远程链接和 IMG-001 归档；来源 FR-012，差距类型 missing。不自行推送或虚构原图归档。

## 阶段 7：新增四工具方向与推理对照

- [x] T013 [US1] 核对现有 GROBID 的真实消费范围，在 `docs/specs/136-complementary-pdf-parsing/four-tool-architecture.md` 展示 MinerU 核心的四工具提案，在 `four-tool-community.md` 核查社区源码；来源 FR-013/SC-008。证据：GROBID 实际 TEI/48 条引用、源码路径和固定提交链接。本项完成的是调查与提案，不是四工具实现。
- [x] T014 [US1] 用 `scripts/complementary_pdf_demo/reasoning_benchmark.py` 比较相同 MinerU 输入的 thinking 开/关，在 `docs/specs/136-complementary-pdf-parsing/reasoning-comparison.md` 保存两组各两次的真实数据；来源 FR-014/SC-009。证据：四次完整输出、共同输入/提示摘要、时间/token/34 项核对与表单限制。
- [x] T015 [US3] 用户确认后更新 Plan、数据模型与生产契约，以 MinerU 主干替换旧 Docling 骨架的生产计划；FR-013/SC-008。证据：2026-10-14 确认、T016–T021 和正式验证；旧实验本身保留。

## 阶段 8：已确认四工具架构的正式实施

用户于 2026-10-14 明确认可架构并授权完整实现，thinking 关闭。T009/T010/T011/T015 的正式接入与契约收敛由下列任务承接；旧 demo 及其负面实验不重写为新架构成功。T012 的远程链接和图片归档仍独立保留。

- [x] T016 [US3] 更新 #136、Spec 和 Plan，补充生产数据与接口契约；FR-013/015–018、SC-008/010/011。证据：最新完整原话、Issue 当前 type:feature 与已确认范围、production.md。
- [x] T017 [US1/US2] 实现 MinerU 主干、Docling/Marker 按页补强与 GROBID 一次调用；保留原始块、版本、坐标、跨度、取用/差异账本；FR-005/006/013/017、SC-003/010。证据：complementary_pdf/IR 与 H3S/CaH6 真实原始制品；跨文件拒绝、原页映射测试。
- [x] T018 [US3] 新 API/UI 固定 complementary，历史方案保持读取；GROBID header 与 bibliography 隔离，DeepSeek thinking 显式关闭；FR-015/016、SC-007/010。证据：HTTP 拒绝旧方案/旧状态读取、前端交互测试、真实 llm_calls.json。
- [x] T019 [US2] 共享科学契约与来源校验，范围参数保留扩展，压力错挂拒绝，原文块引用由服务器展开，保留提取失败原始响应；FR-007/008/017/018、SC-002/011。证据：scientific_contracts、quote_id 身份边界与旧来源回归测试。
- [x] T020 [US1/US3] 完成不同论文真实路径、故障重试、MySQL 来源回读和 Linux runtime 验证；FR-002/010/018、SC-005/010/011。证据：H3S 5 项指定检查/11 个 Claim，CaH6 工作树及独立提交源码真实工作流、Linux MinerU/Marker/GROBID 与 Docling 表格页；分母和限制见 validation。
- [x] T021 回写 Overview、操作说明与验证记录，核验并提交只含本任务的源码，更新 Issue 证据；FR-012、SC-007。证据：Git 多行提交记录、独立源码测试及 Issue 当前验收清单。未推送的远程链接门独立保留，Issue 不提前关闭。
