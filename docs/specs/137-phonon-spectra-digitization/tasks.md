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
