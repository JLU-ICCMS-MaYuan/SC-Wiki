# 实施任务

依据：[spec.md](spec.md)、[plan.md](plan.md)、[research.md](research.md)、[数据模型](data-model.md)、[交互](contracts/interaction.md)。

- [x] T001 创建docs/specs/166-frequency-backtrack-repair/及原图证据，记录已认可需求与算法选择。
- [x] T002 [US1] 在backend/tests/test_spectra_frequency_repair.py编写位移、严格频率、复杂拓扑、端点/低频、轴向和规模测试。
- [x] T003 [US1] [US2] 实现backend/spectra/frequency_repair.py，按局部块生成受限修正并记录。
- [x] T004 [US1] [US3] 集成backend/spectra/recalculate.py及backend/services/spectra.py，验证真实HTTP存储、旧run、幂等与公开过滤。
- [x] T005 [US3] 实现frontend/src/components/spectrumEditor/frequencyRepairs.ts及编辑器撤销/画布高亮/详情报告，补充组件测试。
- [x] T006 [US3] 使用tests/01_decentralized_uploading/下隔离正式浏览器验证重算、定位、撤销、保存和再次重算，记录validation.md。
- [x] T007 更新docs/overview/01_Decentralized_Uploading_of_Superconductivity_Data/spectrum-manual-editor-demo.md和Issue进展；本地提交，不推送。

按T001→T002→T003→T004→T005→T006→T007执行，共享文件串行。未完成任务不勾选。

完成依据见validation.md：T002/T003数学与规模测试；T004真实HTTP/版本/公开；T005组件和绘图；T006浏览器6组场景；T007已回写Overview及Issue，本地提交结果记录于Issue。远程链接门仍未完成。
