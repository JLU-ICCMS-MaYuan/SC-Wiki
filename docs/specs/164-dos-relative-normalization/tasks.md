# 实施任务

输入：[spec.md](spec.md)、[plan.md](plan.md)、[research.md](research.md)、[data-model.md](data-model.md)、[接口](contracts/results.md)。

- [x] T001 在 docs/specs/164-dos-relative-normalization/ 落地已确认文档与原图索引；检查 FR/SC 覆盖。
- [x] T002 [US1] [US2] [US3] 在 backend/tests/test_spectra_dos_relative.py 建立科学数值与条件边界测试。
- [x] T003 [US1] [US2] [US3] [US4] 实现 backend/spectra/dos.py、context.py、contracts.py、discovery.py 并接入 recalculate.py/engine.py。
- [x] T004 [US1] [US2] [US3] [US4] 在 frontend/src/components/spectrumEditor/DosRelativeMetrics.tsx 和 SpectrumDetailView.tsx 展示并切换；新增组件测试。
- [x] T005 [US3] 在 backend/services/spectra.py 核对公开过滤，在后端测试验证新版本、旧记录、人工保存失效和权限。
- [x] T006 [US1] [US2] [US3] [US4] 在 tests/01_decentralized_uploading/ 添加隔离浏览器验收，运行回归与构建，记录 validation.md。
- [x] T007 使用 Overview 技能更新 docs/overview/01_Decentralized_Uploading_of_Superconductivity_Data/data-structure-and-form-mapping.md；更新 Issue 进展；提交结果记录在最终交付说明。

依赖按 T001→T002→T003→T004→T005→T006→T007 串行执行。覆盖映射见 plan.md。先实现独立面积，再增加比例/共同归一化，最后确认原有绝对模式和 α²F 回归。

验证依据：T002–T006 见 [validation.md](validation.md) 的 SC 映射、194 项后端/45 项前端及浏览器报告。T007 的 Overview 已按实际代码回写；远程文档链接门仍未完成。

- [x] T008 [US2] 在 backend/spectra/dos.py 和 frontend/src/components/spectrumEditor/DosRelativeMetrics.tsx 将面积比换算为近似元素比，说明完整频段提示，补充原有测试并更新 Overview。

T008 验证依据见 validation.md「元素比例展示补充验证」；无需原胞 N 或 3N 归一化，限制原样保留。

- [x] T009 [US3] 按最新要求删除 backend/spectra/dos.py 的频段元数据门槛及合同/控件，兼容旧记录，补充测试和文档。

T009 证据：validation.md「删除频段确认门槛」，207项后端、14项前端及构建；旧报告提示重新计算，原始历史数据不批量重写。

- [x] T010 [US5] 更新 #164 与 Spec/Plan/Research/数据及接口契约，保存原话和 IMG-003。
- [x] T011 [US5] 增加 TDOS 门槛失败复现及未知单线/单分波/混合谱等反例，记录修复前失败。
- [x] T012 [US5] 实现基于来源的 total 标记、计算分流、v4 报告/候选与重算/CSV兼容，保留所有独立约束。
- [x] T013 [US5] 更新总谱页面并完成组件、HTTP/SQLite保存重读、真实来源重提取及桌面/窄屏验证。
- [x] T014 同步实际 Overview/验证记录和 Issue；核对本次快照后范围提交，不推送、不部署。

T010–T014：本轮明确授权采用已认可的 TDOS 分流；对应证据见 validation.md「TDOS 独立归一化」。13项失败复现、70项DOS/289项谱回归、55项前端、150项表单、8项变异、字段契约、构建及8项正式浏览器检查通过；真实新描线缺点的失败与沿用人工描线的隔离成功分别保留。业务记录未改写，远程链接仍是独立关闭门。

## 纵轴刻度优先修订

- [x] T015 [US6] 在既有#164与Spec体系记录用户原话、认可及6.30865任意单位·THz示例，同步设计、数据/页面契约与验收；只做文档修订。
- [ ] T016 [US6] 先建立刻度优先/任意单位/无刻度后备的失败回归，再实现当前标定幅值选择和相应归一化，保留独立条件与原始描线。
- [ ] T017 [US6] 页面、保存结果及CSV显示一致的幅值依据、积分单位与范围；旧像素结果不得只换单位标签。
- [ ] T018 [US6] 验证固定人工描线6.30865、倍率等价、缺N/未知身份的独立积分、真实来源处理、HTTP保存重读及相关宿主/谱回归，保留失败证据。
- [ ] T019 实现验收后同步实际Overview、验证记录和Issue，按本次授权范围提交。

T015文档依据：用户“认可，在刚刚的 issue 和 spec 上继续修改。”；本轮只读核算与文档一致性检查见validation.md。T016–T019未执行；既有T001–T014的通过记录不覆盖本轮尚未实现的规则。
