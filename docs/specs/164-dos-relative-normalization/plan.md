# 实施计划：DOS 相对积分与共同归一化

**Issue**：[#164](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/164)
**日期**：2026-10-27
**Spec**：[spec.md](spec.md)

## 摘要与技术上下文

Python 3.12/FastAPI/SQLAlchemy 后端与 React 19/TypeScript 5.6 前端；数值频率统一 THz。存储沿用 SpectrumRun.result_json，不新增表或迁移。pytest 使用 SQLite 隔离 HTTP 测试；Vitest 检查正式组件，Playwright 检查隔离正式页面。目标为现有本地源码，未授权发布。逐曲线线性遍历，不按频率重新排序；一个当前 DOS 集合，不添加其他分析功能。

## 质量门

| 来源 | 要求 | 处理 |
|---|---|---|
| AGENTS | mayuan、保护已有修改、范围提交 | 每次写入/提交前检查分支，明确路径暂存 |
| Spec | 公式与条件不混淆 | 分层结果和独立绝对积分 |
| 技能 | 已批准最终草案、文档先行 | spec.md 记录用户原话和批准；远程链接关闭门未完成 |
| 公共访问 | 不泄露隐藏分波 | 过滤逐曲线结果，移除依赖隐藏曲线的总量和候选 |

## 文档与源码结构

本目录包含 spec、plan、research、data-model、quickstart、tasks、contracts/results、checklists/requirements 与 assets。
新增 backend/spectra/dos.py；集成 recalculate.py、engine.py、context.py、contracts.py、discovery.py、services/spectra.py。
新增 frontend/src/components/spectrumEditor/DosRelativeMetrics.tsx，接入 SpectrumDetailView.tsx。
以现有谱 JSON 承载派生数据；保留 dos_mode_integral 的原始绝对单位语义。

## 需求到设计、任务与验证映射

| 来源 | 设计与事实来源 | 任务 | 验证 |
|---|---|---|---|
| FR-001/002/009、SC-001/005、US1 | dos.calculate_dos；connected_samples；原像素零基线 | T002/T003 | 有效/断线/回折/部分失败 |
| FR-003/004、SC-002/005、US2 | 共同尺度标定、当前材料化学式/结构 | T002/T003 | 比例、无 N、非法/不一致化学式 |
| FR-005/006、SC-002/003/004、US3 | 一个共同倍率、标准定义与已记录裁峰检查 | T002/T003/T004 | 缩放/单位/错误比例 |
| FR-007、US4 | 原始绝对积分单独保留 | T003/T004 | 旧绝对积分回归 |
| FR-008、SC-006 | 新运行保存、手动保存清空派生、公开过滤 | T005/T006 | HTTP、版本、掩码、页面 |
| 全部 | Overview/验证记录/本地提交 | T007 | diff 与明确路径提交 |

## 阶段与依赖

T001 文档 → T002 测试 → T003 计算 → T004 正式展示 → T005 权限及版本 → T006 集成浏览器 → T007 文档收尾。共享文件串行。

## 复杂度说明

相对、归一化和绝对结果分层是科学语义要求；统一一个 available 标志会再次导致全空或误称模式数。不添加外部服务、数据库迁移或新状态存储。

FR-004 细化：dos.element_ratio 计算同参考元素比及最大占比差，DosRelativeMetrics 展示当前化学式；T008 验证无N/缺频段确认/共同比例缩放/零面积/元素错配与界面。

T009：删除频段元数据门槛、输入字段/控件及派生 coverage_note；以版本化报告兼容旧结果。验证无标记/标记false/冲突高频边界/样本未到图框上限均不被该门槛阻断，断线和裁峰仍阻断。
