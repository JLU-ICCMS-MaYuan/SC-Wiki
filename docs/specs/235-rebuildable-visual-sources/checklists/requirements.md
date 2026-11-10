# 需求质量与交付边界检查

- [x] CHK001 原始需求保留旧原文并追加后续实施指令；采用/替代结论在spec.md和conversation.md区分，未把第三方建议当用户命令。[原话核对]
- [x] CHK002 FR-001—FR-013、SC-001—SC-006及US1—US3各有目标、场景和边界，Plan映射到T002—T013。[覆盖核对]
- [x] CHK003 单一视觉主模型、无Qwen部署、首次完整图注、300/600 DPI、来源定位重建及5次技术重试在共同框架一致。[跨Spec约束]
- [x] CHK004 各Feature有唯一type:feature的实际Issue，Spec回链指向#235；Issue更新后还需回读正文/标签。[Issue核对]
- [x] CHK005 数据模型与接口只定义内部来源/观察协议，科学标准键、审核权限及四宿主契约保持原职责。[FR/数据所有权]
- [x] CHK006 本轮按实施授权写入实际代码/测试/Spec及Overview；并行任务改动排除在本地提交外，按验证字节核对。[本轮范围]
- [x] CHK007 后续明确实施授权已逐字追加；不把技术文件存在冒充额外逐字审阅。[确认边界]
- [ ] CHK008 原PDF新模型、固定失败、专用后处理、存储/快照/RAG、四宿主和变异实际运行通过。[SC/未来验收]
- [ ] CHK009 本地Spec和截图推送后远程链接实际访问成功；未授权不push。[远程文档门]
- [ ] CHK010 实现后的Overview/必要README同步及Issue关闭检查完成。[Documentation Impact]

CHK001—CHK006的本地文档证据见validation.md及[#232跨Spec核验](../../232-complete-pdf-regions/documentation-audit.md)。未完成项不因本轮文档整理而勾选，不声明全部实施门已通过。

本轮实现、运行证据与剩余科学/远程门以validation.md为准；CHK008—CHK010不因已有本地实现或Overview更新而自动视为完整关闭门通过。
