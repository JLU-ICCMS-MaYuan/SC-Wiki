# 现有接口合同增量

不新增URL，不改变权限、布局和按钮。

- preflight：按当前原文与规则验证历史条件，输出已有supported/stale/required；可附review_revalidation、review_attempt和invalidation_details用于审计。失败尝试不得覆盖仍有效凭证，有效冲突必须撤回。
- proposals：保留expected_version与字段身份校验，合法可空成员不再被类型误拒；非启用值槽不得填入其他类型。当前规则已通过且值未变的paper_inference可正常保存/接受，human_confirmed保持false。
- prepare/finalize：原样接受不重建丢失条件策略的claim；保留有效rule_review与association_review，持久化后仍重验，不能丢失资格或伪造人工确认。
- 来源/规则版本变化：不得无条件改旧hash。支持有界原文重验产生新的当前结果，保留旧记录。
- 失败恢复：既有重试入口继续使用；前端仅在授权范围内修复共用字段按组定位与父级变更通知的失效判断，不改变页面布局和按钮。浏览器需证明输入保持、错误退出忙碌、重试请求使用当前版本。

验证与限制见../validation.md；未执行的链路不能称作完成。
