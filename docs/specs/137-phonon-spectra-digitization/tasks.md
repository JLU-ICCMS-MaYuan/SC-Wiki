# 实施任务

输入：[spec.md](spec.md)、[plan.md](plan.md)、[research.md](research.md)、[data-model.md](data-model.md)、[contracts/demo.md](contracts/demo.md)。

- [x] T001 固定 scripts/phonon_spectra_demo/cases/h3s-2014.json 的来源、坐标和结构证据。[validation.md：两份来源及结构实测]
- [x] T002 [US1] 实现 scripts/phonon_spectra_demo/digitize.py 的线性标定、提取、有界插值和缺失语义。[validation.md：合成图与真实八条曲线]
- [x] T003 [US2] 实现 scripts/phonon_spectra_demo/build_demo.py 的结构计数、共同归一化候选和独立积分诊断。[h3s-2014-report.json；科学限制保留]
- [x] T004 [US1] 在 scripts/phonon_spectra_demo/tests/test_digitize.py 验证已知曲线、换轴、缺口及输入异常。[14 项通过]
- [x] T005 [US3] 实现 scripts/phonon_spectra_demo/template.html 的材料状态、原图回绘、图表、点表和导出。[真实浏览器交互及实际下载核验]
- [x] T006 [US3] 生成 demo/phonon-spectra/ 真实产物，执行数据往返与桌面/390px 浏览器检查，记录 validation.md。[4654 点往返一致，页面无溢出]
- [x] T007 核对需求覆盖、科学限制及本次 Git 提交边界，更新本目录验证记录。[analysis.md、validation.md；不代表用户科学验收]
- [ ] T008 [US3] demo 获用户验收后细化正式谱数据表单、持久化、审核及导出合同；本次不执行。
- [x] T009 [US1] 修复 scripts/phonon_spectra_demo/digitize.py 的暗色虚线漏检与图框平台端点；同步 build_demo.py、template.html 的补读来源，增加 tests/test_digitize.py 回归并复核八条真实曲线。[FR-008、SC-007；validation.md 暗色虚线补读：20 测试、64→0 缺失、3180 原观测不变]
- [x] T010 [US2] 在 scripts/phonon_spectra_demo/quality.py 增加原图零基线候选与累计谱矩独立核验；build_demo.py 记录条件模式数对照和完整验收元数据，template.html/CSV 展示候选；tests/test_quality.py 验证独立真值与原数据保留。[FR-009、SC-008；27 测试、4654 点未改，见 validation.md 精度核验]
- [x] T011 [US2] 按用户要求执行科学复核，修复 digitize.py 的零频首区间遗漏，新增 scientific_review.py 独立核验和数据绑定，落盘 scientific-review.md/JSON，并由 build_demo.py、template.html 展示用途分级。[FR-010、SC-009；34 测试，定量训练未通过不等于复核未完成]

## 依赖与覆盖

T001 → T002 → T003；T004 验证 T002/T003；T005 → T006 → T007。FR-001/003、SC-001 对应 T001/T003；FR-002、SC-002/006 对应 T002/T004；FR-004/005、SC-003/004 对应 T003/T004；FR-006/007、SC-005 对应 T005/T006。T008 是后续生产阶段，不因 demo 完成而勾选。

本轮用户再次指定只做 demo 精度与验收，T010 为本次交付；T008 继续保持未执行。软件自动核验完成不代表用户已采纳科学候选。

- [x] T012 [US1/US2] 修复 scientific_review.py 的虚线插值误判及真实观测域边界，增加 joint_reconstruction.py 原图范围与留出验证；更新 build_demo.py、template.html 的联合候选、掩膜和用途语义；增加 tests/test_joint_reconstruction.py 及原图派生证据，保存科学复核 v5 更正。[FR-011、SC-010；40 测试，两相每相 70 留出点，validation.md；T008 未执行]

## 正式接入任务

T008 的实施范围现已明确授权，由以下步骤落地，原 demo 阶段记录保留。

- [x] T013 建立正式阶段契约和需求映射，保留用户原话。[production-plan.md、contracts/production.md；用户完整确认]
- [ ] T014 移入共享算法，自动找图与模型标定，生成分项质量报告。[代码与原40/新增15项测试、真实PDF来源发现已完成；完整模型标定因503未验收，不勾选主路径完成]
- [x] T015 新增谱集合/运行迁移和持久化、版本、权限服务。[隔离MySQL迁移、事务回滚、版本和公开掩膜HTTP实测]
- [ ] T016 接入 RQ、自动上传、事务提交与返修及状态导出。[代码、真实RQ重提取、隔离事务绑定/返修拷贝、Redis恢复及导出已验证；新上传全自动标定到正式提交仍待模型服务恢复后闭环验收]
- [x] T017 三入口共用质量组件、标定修正、逐谱审核及下载。[43项前端回归；真实浏览器三个入口、390px、CSV实际下载]
- [ ] T018 原40测试、独立合成PDF与真实H3S自动提取验证。
- [ ] T019 隔离数据库和真实浏览器验收，回写 Overview/README/Issue，只提交任务增量。

T018/T019 保留未完成：当前 GPT-6-sol 服务随机图成功，但 H3S/独立合成谱完整标定返回503过载，不能标科学自动验收通过。业务库迁移与部署仍按计划单独执行。本轮保留已验证代码，但整体验收未完成；遵守AGENTS.md暂不提交，不关闭整个Feature。

T019的代码文档与隔离验证已落盘，但完整模型验收和业务部署未完成，本轮未提交、未推送，不等同Feature完成。

- [x] T020 [FR-013/SC-012] 完成本机业务库备份、定向增表迁移、部署清单同步、双表就绪检查及 #94 独立详情兼容回归；实际页面核验后仅提交 #137 文件，保留模型自动标定验收限制。

T020 完成依据：validation.md 的 2026-10-15 本机迁移记录、assets/local-migration-20261015.json、local-http-20261015.json、local-browser-20261015.json，以及独立候选测试。仅完成迁移与技术交付里程碑；T018 和完整 T019 不因本次提交而勾选。此前“不提交”的描述为 2026-10-14 阶段历史，本次用户已明确授权并要求提交已验证增量。

- [ ] T021 [FR-012/FR-013] 通过 SC-Wiki 正式异步 API 对已有 La-Sc-H 上传任务提取 DOS/α²F，保留正文及补充来源、模型/状态/质量及失败事实；修复旧任务缺可选 IR 时错误中断原 PDF 找图的问题，并验证后提交。不得用人工标定或外部脚本产物代替平台结果。

- [x] T022 [FR-012/FR-013/FR-015] 修复缺 IR、空结果成功缓存、失败状态与原因；扩展 olive、组合上下图片碎片、矢量图框裁剪与文字页排除，升版 v2；原数学与后端 69 项、谱前端 11 项和构建通过。平台 v1 实跑见 assets/lasc-platform-run-20261015.json，v2 不冒充真实模型已重跑。

T021 保持未完成：平台实际保存 3 条 DOS 与 1 条累计 λ，均待分配；α²F 尚无数值。GPT-6-sol 多图请求返回 HTTP 503，且 v1 颜色范围和图碎片导致信息缺失。用户要求查看配置以自行核查，已告知 .env 的 LLM2_BASE_URL / LLM2_API_KEY / LLM2_MODEL；待核查后继续用正式 API 重跑，不导入手工数据。

- [x] T023 [US7/FR-016/SC-013] 按用户已认可的 assets/spectra-navigation-demo/ 原型核对并完善 frontend/src/components/PropertySpectra.tsx、frontend/src/pages/SpectrumDetailPage.tsx 的按材料状态分类、两个明确入口、独立详情及返回定位；未归属候选单列，无数据状态不串用其他谱。补充 tests/01_decentralized_uploading/property-spectra-navigation.test.tsx 与真实浏览器／权限／数据归属验证，将实际结果记入 validation.md 后再勾选；Demo 认可不代替生产或科学验收。

T023 使用既有谱数据身份与详情路由，依赖 T015/T017 的已验证基础，和 T021 的真实数据可用性分开记录；不更改 T018/T019/T021 的未完成状态，不在本次确认记录中实施。


- [x] T024 [FR-012/FR-015] 用户更新 API 后重启并核对任务快照，通过 SC-Wiki 正式 API/RQ 实跑 La-Sc-H；兼容可选零证据空数组，明确排除图内 λ 注记；核验三压力的 DOS/α²F、CSV/JSON、当前状态重算及实际浏览器，保存 assets/lasc-new-api-20261015.json/png。后端/原算法 73 项通过。

T024 更新 T021 的历史进展：当前 290/300/350 GPa 的 La/Sc/H DOS 和 α²F 均有平台候选，最新一轮另有 290/350 GPa 累计 λ。首次完整输出为 15 条，重读后为 14 条；旧数值仍在历史版本，不拼接。六组当前候选无 stale，但均未采纳；T021 的完整科学质量核对与候选收敛仍未完成。本次 API 重试完成，不把 T018、T019 或 T023 的验收一并勾选。

T023 完成依据（2026-10-15）：正式组件的谱导航 18 项、共用工作区 2 项，邻接统一表单／折叠／上传布局 56 项回归；共享数学及后端 73 项，隔离 MySQL 3 项（含真实 HTTP 归属、双版本冲突、无关用户读写拒绝、旧运行保留及采纳失效）；生产构建通过。浏览器使用实际平台数据副本验证 DOS／α²F 入口、原图、空结果候选、返回聚焦、归属重算、匿名拒绝和带来源 CSV；390px 下页面宽度保持 390。完整结果与界限见 assets/navigation-production-20261015.json。此前“不在本次确认记录中实施”为认可记录阶段，此后用户明确要求开始执行；不据此改变其他未完成任务或关闭整个 Issue。
