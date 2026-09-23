# 规格分析：多模态 PDF 解析与证据驱动上传 Agent

**分析日期**：2026-09-23

## 一致性结论

- **CRITICAL**：无。
- **HIGH**：无。Issue、Spec、Plan、Data Model、Contracts 和 Tasks 的目标一致。
- **MEDIUM**：具体 PDF LLM 供应商和 50 篇论文数据集来源尚未固定，但已写入假设和 T002/T003，不阻断接口设计。
- **LOW**：Docling/MinerU 的具体版本需在 T001 根据目标 Python 与镜像验证后固定。

## 覆盖检查

| 范围 | 覆盖任务 | 验证 |
| --- | --- | --- |
| Document IR 和解析器 | T004–T014 | parser 契约、样例和 fallback 集成 |
| Claim 和 Evidence | T006、T015–T019 | 定位、来源类型、迁移和提交回归 |
| 覆盖与 Agent | T007、T020–T023 | 表格行、工具预算、失败收敛 |
| 区域证据 UI | T024–T027 | API、渲染、上传/审核浏览器验收 |
| Rollout | T003、T028–T031 | Shadow、灰度、质量门和回滚 |
| 文档与收尾 | T032–T036 | Overview、README、验证、Issue 门禁 |

## FR/SC 追踪统计

- 功能需求：14/14 有任务映射。
- 用户故事：5/5 有独立验收阶段。
- 成功标准：8/8 有测试或基准任务。
- 关键实体：7/7 有数据模型或接口契约。
- 文档产物：全部存在，契约文件覆盖 parser、IR、Claim、Agent 和 rollout。

## 允许的实施调整

如果 T001 发现某个依赖无法在目标 Python/镜像稳定安装，必须先更新 Research/Plan 和 Issue 边界，再修改 requirements，不得静默换成未审查供应商。若 PDF LLM 服务不支持文件输入，必须退回页面/区域输入适配器，不降低 Evidence 校验要求。
