# 数据与生命周期

复用ScientificEvidenceCheck.result，不新增表。现有item_key表示字段身份；content_hash绑定当前科学claim，source_hash绑定当前原文/来源角色及完整性。条件策略版本为condition-rules-v2，不再包含Tc端点/μ*作为条件身份。

- rule_review：已有规则凭证，仍保存范围、版本、来源覆盖和可定位证据。
- review_revalidation：当前版本按原文重验旧条件后的说明，包含旧内容摘要及旧规则版本；不改历史行，不等同人工批准。
- review_attempt：保留本次未通过的尝试原因、实际请求时间等；与仍有效的条件凭证分开。
- condition_conflict：模型各来源窗口中的明确规则冲突，防止聚合为uncertain后丢失反证。
- condition_window_errors：保存本次窗口校验缺口，不能作为科学反证或未报告结论。
- invalidation_details：无法沿用时的具体变化类别，附于原有理由，不新增页面。

已知v1历史条件只在完整旧claim匹配其摘要、当前事实/必要依赖等价、来源覆盖相同且当前规则重验所有原文成功时可产生新投影。v1字段绑定用legacy_leaf_claim重建对照，不能删旧指纹猜测等价。未知版本、证据篡改、来源变化或有效新冲突拒绝继承。

Tc结果行的非谐归属由结果字段独立检查。共享条件通过不等于新增Tc配对通过；缺少原表归属时只让相应结果待核对。

保存未采纳的草稿和保存核对决定均有类型约束；value_kind启用槽必填且类型正确，未启用槽只能为空。人类最终批准与paper_inference身份保持原合同。
