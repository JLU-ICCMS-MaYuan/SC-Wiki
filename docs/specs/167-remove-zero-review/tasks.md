# 实施任务

依据：[spec.md](spec.md)、[plan.md](plan.md)、[research.md](research.md)、[data-model.md](data-model.md)、[契约](contracts/behavior.md)。

- [x] T001 核对前两项修改回写#161，创建#167及完整文档和关联。
- [x] T002 在backend/tests/test_spectra_no_zero_review.py建立正起点、无确认、真实数学异常和实际区间测试。
- [x] T003 修改backend/spectra/samples.py、manual.py、preflight.py、relative.py、dos.py、frequency_repair.py，删除核对依赖并保留数值有效性。
- [x] T004 修改backend/spectra/engine.py、digitize.py、discovery.py，使用通用刻度和ROI，不要求零刻度/扩展到零。
- [x] T005 删除正式frontend/src/components/spectrumEditor及Demo src中的人工核对模块/控件/类型和废弃样式，更新旧记录兼容与关联测试。
- [x] T006 验证后端、正式前端、Demo测试/构建和隔离浏览器；检查连续保存、版本恢复与回折修正不退化。
- [x] T007 同步Overview、验证记录和Issue状态，仅明确路径本地提交；远程链接未核验不关闭。

按顺序执行，测试与实现实际完成后勾选。

验证依据：[validation.md](validation.md)。T007的本地实现、文档与提交收尾不代表远程链接已可访问，Issue继续保留远程核验门。
