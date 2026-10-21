# 实施计划

Issue：[144](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/144)。日期：2026-10-21。依据：[spec.md](spec.md)，用户明确授权执行建议。

## 方案与边界

1. 保存合同：在evidence_proposals中按字段名称及value_kind表达可空性，递归用于扩展对象；未启用值槽可空、启用槽仍严格校验。保留来源与身份保护及现有validate_record领域校验。规则通过的paper_inference可原样接受，不伪造人工确认。
2. 条件与结果：condition_rules的条件策略不再纳入Tc结果数字；非谐结果归属在结果字段检查，不能以条件事实通过替代结果归属。数字只作定位辅助，不能反向使条件事实过期。
3. 旧证据：独立的condition_lifecycle模块只对已知旧版本、完整旧claim、相同来源、值/必要依赖/范围等价的条件重新验证证据。重新生成当前通过投影，保留旧核对记录；不直接给旧关联改摘要。缺证或新有效冲突不能恢复。
4. 失败与结论：有仍有效的旧证据时，新一轮技术失败或漏引单独记录尝试，不丢失有效结论；真实反证/缺失/来源变化仍撤回。复用现有核对JSON与事务，不新增数据库表或公开API。
5. 验证：单元正反例、真实草稿只读对照、MySQL回滚持久化、完整编辑器浏览器操作（新增/输入/保存/刷新/重开、侧栏与定位），分别记录非谐归属、标红、焦点和滚动结果。

## 技术上下文与文件

Python/FastAPI/SQLAlchemy/MySQL/Redis，前端React/TypeScript/Vite。验证工具为现有pytest、Vitest和Playwright浏览器脚本。优先修改backend/ingest/evidence_proposals.py、condition_rules.py、scientific_evidence.py及新增condition_lifecycle.py；若必要触及property_evidence.py仅提交本次增量。前端布局零改动；已单独获准修改evidenceFields.ts与EvidenceWorkflow.tsx中的共用字段定位及失效逻辑；其他任务已改文件先保留基线。

## 需求映射与质量门

| 需求 | 实施任务 | 验证 |
| --- | --- | --- |
| FR-001/002/007，SC-001/004 | T002/T003 | 保存往返、非法值、人工身份反例 |
| FR-003/004/005/006/011，SC-002/003 | T004/T005 | 值/来源/范围变化、旧版兼容、冲突与失败 |
| FR-008/009/010/012，SC-005/006/007 | T006/T007 | 浏览器全流程及真实存储、版本与备份 |

原话与新授权已核对；已确认科学规则不再重复询问。实现不改变数据所有权、权限或批准入口。未知跳动根因不预先标记已修复。远程文档未推送，不关闭Issue；不把该链接限制误当成禁止已授权本地实施。
