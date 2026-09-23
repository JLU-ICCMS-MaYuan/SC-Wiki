# 规格分析：多模态 PDF 解析与证据驱动上传 Agent

**分析日期**：2026-09-23

## 一致性结论

- **CRITICAL**：无未解决项；原有“自动降级为另一解析器”的表述已改为任务选择解析方案，指定方案不可用时失败、重试或转人工。
- **HIGH**：Native PDF LLM 已明确只返回 Document IR；Claim 由独立步骤生成；`reading` 子状态不扩展既有五阶段；正式定位通过 `paper_evidence_locators` 关联现有 Evidence；升版只保留新的当前 revision 完整文档。
- **MEDIUM**：具体 PDF LLM 供应商和 50 篇论文数据集来源尚未固定，但已写入假设和 T002，不阻断接口设计。
- **LOW**：Docling/MinerU 的具体版本需在 T001 根据目标 Python 与镜像验证后固定。

## 覆盖检查

| 范围 | 覆盖任务 | 验证 |
| --- | --- | --- |
| Document IR 和解析器 | T004–T014 | parser 契约、方案选择、媒体路由、样例和失败收敛 |
| Claim 和 Evidence | T006、T015–T019 | 定位、来源类型、定位关联表、迁移和提交回归 |
| 覆盖与 Agent | T007、T020–T023 | 表格行、工具预算、失败收敛 |
| 区域证据 UI | T024–T027 | API、渲染、上传/审核浏览器验收 |
| Rollout | T003、T028–T031 | Shadow、灰度、质量门和回滚 |
| 文档与收尾 | T032–T036 | Overview、README、验证、Issue 门禁 |

## FR/SC 追踪统计

- 功能需求：14/14 有任务映射。
- 用户故事：5/5 有独立验收阶段。
- 成功标准：8/8 有测试或基准任务。
- 关键实体：8/8 有数据模型或接口契约。
- 文档产物：全部存在，契约文件覆盖 parser、IR、Claim、Agent、定位关联表和 rollout。

## 允许的实施调整

如果 T001 发现某个依赖无法在目标 Python/镜像稳定安装，必须先更新 Research/Plan 和 Issue 边界，再修改 requirements，不得静默换成未审查供应商。若指定 PDF LLM 方案不支持文件输入，必须由任务显式选择页面/区域方案，不得在同一次运行中静默切换，也不得降低 Evidence 校验要求。
