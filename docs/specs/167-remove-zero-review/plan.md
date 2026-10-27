# 实施计划

日期：2026-10-28。Issue：[#167](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/167)。依据：[spec.md](spec.md)。

## 技术上下文与职责

Python3.12/FastAPI、React19/TypeScript5.6；现有SpectrumRun JSON和Document，无新表。
后端samples移除确认/首点零限制；manual退休zero字段与报告；preflight不再生成确认/低端覆盖诊断；engine/discovery/digitize使用通用刻度与ROI而不强制零频；relative/dos如实记录起止区间；frequency_repair只保留数值保护。
正式和Demo删除zeroCheck/ZeroFrequencyCheck，清理Editor/SourceCanvas/engine/adapter/axisGeometry专用流程，保留普通轴刻度和标定。新方法版本避免旧阻断结果继续作为有效提示。
测试：pytest、Vitest、Demo测试/构建、隔离FastAPI/SQLite与本地5173浏览器。仅改指定文件，保护两个已有dragInfluence.ts修改。

## 需求与任务映射

| 来源 | 事实与设计 | 任务 | 验证 |
|---|---|---|---|
| FR-002/003/005/008、SC-001/002/005 | 当前采样、分段线性公式、真实区间 | T002/T003 | 正起点解析值、f=0真实发散、无确认 |
| FR-001/004/007、SC-003/004 | 轴刻度与ROI、UI退休/旧数据降级 | T004/T005 | 无UI流程、旧记录与无零刻度 |
| FR-006/009、SC-004/006 | 数值保护、既有版本和参考 | T003/T006 | 回折/保存/版本回归 |
| 全部 | 已实现行为与证据 | T007 | Overview/Issue/提交 |

## 设计取舍

人工确认与数学积分分开；取消用户步骤不等于强制把数据补到0或把发散结果变成有限值。
α²F/DOS结果记录actual区间，λ参考归一化政策不改。普通图框/坐标合法性继续校验；正频首点不构成错误。
旧确认字段只在读取边界忽略；历史原始记录不迁移，移除运行代码后不维护另一套legacy核对状态。
