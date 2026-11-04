# 解析流程展开、侧栏诊断与审核历史写入修复

关联 [#147](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/147)、[#109](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/109)、[#172](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/172)、[#174](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/174)。日期：2026-10-29。

## 原始需求记录

> 字段提示规则及相关历史已迁移至 [#220](../220-field-red-marking/spec.md)，本处不再独立定义。

三张原始截图按顺序归档为 [IMG-001](assets/2026-10-29-flow-review/IMG-001-system-parse.png)、[IMG-002](assets/2026-10-29-flow-review/IMG-002-cah6-diagnostics.png)、[IMG-003](assets/2026-10-29-flow-review/IMG-003-approval-gate.png)。原名、尺寸、顺序与 SHA-256 见[图片清单](assets/2026-10-29-flow-review/images.json)。截图属于现象材料，不作为新的科学批准指令。

## 当前状态与原因

1. 字段提示规则及相关历史已迁移至 [#220](../220-field-red-marking/spec.md)，本处不再独立定义。
2. **长诊断没有进侧栏**：#109 的[已确认展示规则](../109-field-evidence-and-ai-suggestions/source-review-presentation.md)已经明确主表单只留紧凑标记和数量。#172 后加的 ParsingDiagnosticsPanel 独立展开题录及六类差异，没有继承这项展示约束。问题是后续实现没有衔接既有规则，不是用户没有提出要求。
3. **La–Sc–H 批准失败**：论文 271 仍为 pending、内容版本 1，上传者为用户 2；超级管理员为用户 1，不触发禁止自审。当前 1111 个字段摘要全部 supported，实际门禁只读重建没有阻断项，格式校验通过。已有服务日志中两次 review-commit 返回 500，栈落在 paper_history_events 写入，出现 MySQL 连接重置及数据包序号异常。按当前正式核对结果重建的历史 JSON 为 398,343,401 字节，超过当前 max_allowed_packet 的 67,108,864 字节。重复 legacy_evidences 约 333.6 MB、validation_record 约 51.8 MB，是主要膨胀来源。

日志异常单独不足以证明包大小根因；本轮同时核对了具体失败 SQL、真实 JSON 大小、数据库限制，并验证去重后的同一结果可实际写入、重读与无损恢复。

## 修复边界与实现

- HTML 主流程中点击“系统解析与 AI 提取”“批准前检查”，弹出各自六步详细流程；保留侧栏概要，支持关闭、Escape 与键盘，未连接真实任务控制。
- 解析诊断只在主表单保留入口与紧凑数量，题录、类别、代表例、原图及原始记录进入右侧栏；关闭恢复入口焦点，定位字段时关闭侧栏并回到当前字段。原文仍按点击加载。
- 科学待处理入口在确有科学问题时使用红色，数量及问题定位继续由现有状态规则决定。未完成、过期、技术故障不伪造成科学错误。
- 批准历史只改变重复上下文的存储方式：每条 evidence_review 保留原值、字段身份、来源版本、决定、理由和出处；legacy_evidences 与 validation_record 按内容哈希共享到 history_contexts.values，字段通过 `_history_context_refs` 引用。池版本为 1，按引用恢复两字段即可重建原记录。旧审核结果、永久来源及科学门禁不变，不删除历史资料、不调大数据库配置、不新增数据库表。
- 同一真实样本去重后为 17,231,903 字节，低于当前 64 MiB 单包限制。Go 历史接口使用的字段及来源仍保持原结构，无需改变既有展示协议。

## 验证

- 先修改解析展示回归，证明旧页面仍在正文展开题录与类别而失败；修复后测试侧栏按需展开、来源快照不因无关输入重分组、真实题录变化失效及关闭焦点恢复。
- 新增审核历史回归通过实际 commit_review 调用路径构造超过 64 MiB 的重复上下文；旧实现因整段重复 JSON 超限断言失败。修复后小于 2 MiB，逐字段内容、人工决定、引句及全部共享上下文还原与原数据一致；不修改输入对象。
- 当前真实 1111 字段结果生成的 17.2 MB 历史，在新建的隔离论文外层事务中调用正式历史写入服务，写入、重读及全部字段无损恢复通过；外层事务回滚后隔离论文不存在。没有对论文 271 执行批准。
- 两个 MySQL 既有用例覆盖批准原子应用及科学不通过阻断通过。`human` 用例在确认一个已经 supported 的字段时被既有规则拒绝；用 HEAD 原模块独立复跑仍同样失败，不能计为本次通过。
- `test:form-contract` 64 项通过，覆盖上传、返修、管理员与超级管理员完整宿主；`test:form-contract:mutation` 检出四宿主共 8 项已知缓存回退。前端构建通过。
- 扩展检查 source-review-presentation 与 scientific-evidence-markers 两套测试，当前为 12 项通过、9 项失败；以 HEAD 原 EvidenceWorkflow 和 ParsingDiagnosticsPanel 的临时编译器覆盖独立复跑，仍是完全相同的 9 项失败。保留基线证据，不将这些旧失败写成通过。
- 实际 CaH₆ 草稿和摘要只读复制后使用正式上传路由及隔离 API 验证：主表单不再展开六类明细，侧栏内容可读；5 项待处理入口为红色；关闭恢复焦点；输入期间无请求、无全表字段扫描；390px 窄屏可打开侧栏。HTML 的两个详细流程分别有六步，点击、关闭、Escape 与窄屏通过。

本地原始诊断与结果在 `.data/pdf-flow-investigation-20261029/`，基线输出为 `/tmp/scwiki-flow-related-baseline.log`，本次对应输出为 `/tmp/scwiki-flow-related.log`。临时文件不作为长期协作状态入口。未重新解析 PDF、调用模型重核、覆盖用户草稿、代替用户批准、推送或部署。
