# 人工问题队列与局部恢复验证

2026-11-12在mayuan实施。首题无科学稿也先提交ScientificUploadDraft.state，SQL权威、Redis镜像；普通保存不能覆盖新题和答案。逻辑身份由输入、目标版本、冲突与来源关系组成，不按理由措辞去重。

recommended/investigate/manual三入口，不答不应用；答案幂等、作者校验、过期输入保留。无关题追加允许旧queue_revision，本题prompt_revision、target_token、输入及目标版本仍须相同；超前revision拒绝。字段及结构候选有窄接入口；人工方向仅投影相应目标，人工资料沿ScientificManualEvidence保存，不创建approve。

材料组保留completed/waiting_human、原候选去向及完整检查点；前组待答后组继续，恢复复用填写和有效结果，只补问题及现有真实依赖。只剩待答进入paused/pause_reason=human_questions释放Worker；答案经原模型与正常RQ续跑。科学补查仍未解决则保持待答，不循环刷新动作预算。

## 实际验证

- 新回归先检出缺少模型工具入口；修复后冲突入队、同批邻字段继续。
- SQL新会话覆盖首题、去重、幂等、权限、过期、事务失败、旧保存防覆盖、字段人工材料保存重读及不生成approve。
- 真实UploadModelActivity宿主覆盖三入口、不答、失败输入与幂等重试、追加问题保留中文输入及焦点；旧任务零问题请求。相关12项通过。
- 独立Redis/SQLite/真实RQ覆盖Worker完成释放、人工暂停、实际删除Redis缓存后SQL恢复、真实HTTP读答、正式process_upload_task续跑入队、重复答案不重复入队和其他超管403。证据：tests/TestForRealScenario/runs/20261111-peng2017-flash-clean-01/human-question-runtime.json。未执行第二次论文Worker，不当作整篇黑盒。
- 后端相关128项、四宿主250项、12项变异及字段契约通过；TypeScript/生产构建通过。未声称远端CI运行。

真实文献题目、第二次Worker局部补做、正式交接与五阶段继续随Y-H黑盒记录，不据隔离探针勾选全部业务验收。


## 原PDF新模型的实际边界

LaH9和ScH10定向字段的新Flash调用均未产生问题，不将它们冒充真实答题链。ScH10首次结果的理由承认原文冲突但标supported，发现最终结果缺少明确分流声明，现要求同一次结果给resolution；后次模型声称可解决，不以程序解析自然语言替它改科学结论。前次完整输出因早期辅助脚本未分轮而被后次覆盖，实际工具捕获摘录保留于backend/tests/fixtures/human-question-conflicting-supported.json，并明确不称完整原生响应；脚本已改时间戳分轮。固定重放确认缺resolution不能直接通过，显式human_required即使附supported也进入待答。模型未识别的科学冲突仍需真实原文校对及既有人工裁定，不能用新规则或额外分类模型掩盖。


## 人工资料归属回归

先由humanq-preserve-before.log检出旧人工文字被重建、来源身份丢失；修复后9项队列回归通过。新方向使用原text_file附件类型，走既有add_file和保存/交接链，原文字、理由、作者与来源保持。模型输入和保存附件使用同一answer_material字节/摘要，仅实际送达模型后记录已读；不新增科学字段、证据核对步骤或不同科学预算。
