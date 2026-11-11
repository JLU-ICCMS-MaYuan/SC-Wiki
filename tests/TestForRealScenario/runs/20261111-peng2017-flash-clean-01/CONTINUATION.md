# 接续入口

## 当前目标与不能宣称的结果

完成Peng2017 / Y-H双视觉模型完整五阶段黑盒，并按用户流程完成重新上传后无需调试的复测。**整体未完成。** GPT排障轮实际五阶段已走通，论文1485已按流程定向清理；Flash本轮仍未完成第一阶段，没有正式论文ID。

流程：`tests/TestForRealScenario/document-upload-blackbox-workflow.md`。

## 已完成与源码

- GPT排障轮完整报告：`../20261111-peng2017-flash-blackbox-01/GPT-DEBUG-ROUND-REPORT.md`；45物性记录／31结构回读一致，2009字段选定来源使用关系零变化，探索YH10实际打开1485。完整科学图和展开交接历史gzip归档后，网页清理1485及旧Flash任务0f9ed...；其他271/1204/1429保持，原PDF保留。
- 本地提交：a9a9f648来源／人工依据交接，b482bd30原断言背景保留，9ff312f1原生严格传输／结构归属与GPT报告，c6c2d314当前图成功工具观察复用与精确刻度错误反馈。分支mayuan，未推送／部署。
- 新Flash任务 `b5a836764aa24e7cbb88b243a1ed2768`，新Job `c0f9925e-2cc3-42c4-b622-be4602a35ab6`，generation2。实际LLM1/deepseek-flash，官方api.deepseek.com；两原PDF角色、大小、SHA256匹配。
- 本轮源于9ff312f1的全新上传，最初Fig4耗尽13动作而失败，之后修过代码，**目录虽名clean-01，已转排障轮，不算最终无调试轮**。失败完整模型／工具响应在first-failure-model-archive与first-failure-chart-archive。
- 两新故障先检出，再修复；43项图读／反馈／增量／基线回归通过。正文Fig4新模型读数经正式标定与IR保存重读，38条与同原PDF独立原位图参照零差异；见main-fig4-independent-comparison.json、main-ir-after-chart-repair.json。工具成功观察10→20→38复用，4次新请求，原预算13不变；PrH9两个0K仍是用户裁定，不宣称自动识零。

## 最新阻塞与用户待答复

SI第13页Fig.S14：模型实际digitize_image_elements参数外层有panel对象，但里面缺必填panel字符串。程序按#205严格拒绝；不是503、不是上下文超限，不猜面板名、不靠重试刷过。

原始失败与request/prepared-request已外存model-failures。规范请求确有strict:true、nested required panel，提示词已明确arguments.panel.panel。官方Chat/beta的带json_object与不带JSON模式两项简短对抗探针均漏该字段；官方Responses原生工具同样漏；Responses text.format=json_schema最初通过，但后续3项对抗中仍1项漏字段且加未知键，不能声称strict生成可靠。第一次误用/beta/responses返回400只是错误入口，不计能力证据；已查官方/guides/responses_api，正确入口api.deepseek.com。

证据：deepseek-required-field-transport-probes.json、deepseek-responses-official-required-probes.json、deepseek-responses-adversarial-json-schema.json。原型program-owned-panel-identity-proposal.json只在隔离副本把当前轴344.6–611.4唯一匹配原图几何带344.598–611.367，再分配panel-geometry-f27a865c2ba0c9aa；其余值和来源全等、canonical schema通过，**未执行图片工具、未写业务数据、未进行科学验证**。

已通过request_user_input_async问用户：是否采用“程序管理面板技术身份”：仅原图几何唯一匹配才分配稳定ID，保留模型原始标签，不补科学值、不增加AI调用或预算，不能唯一定位继续停。选项：采用（推荐）／保持原协议暂停Flash等上游／先讨论。**尚未获答复，不能实施或继续依赖此方案。** 原#205 FR-003“仅字段结构错误不再触发额外模型纠错”及用户“改变既有设计先审查”是本次必须等裁定的依据。不可把重复请求结构错误当传输重试。

## 浏览器与恢复

- 新Flash Safari隔离窗口22617，upload、account及task详情几个标签；按完整URL重枚举，别沿用标签号。account已核验myth620137018@163.com、用户；当前选LLM1。任务URL http://127.0.0.1:5173/upload/tasks/b5a836764aa24e7cbb88b243a1ed2768。
- Chrome超管1758018215为superadmin?section=papers&review_tab=history，实际待检查页；1758018117为account，mayuan_mark@163.com已核验。Chrome模型仍LLM2。
- 旧Safari22551是已清理Flash详情，22561是GPT探索和已清理1485详情；22164两个已清理1485详情及account，19508旧GPT详情及account；18044/19414为upload。只操作本轮新任务，旧详情不代表有效草稿。
- `browser_action.py`本轮副本按完整URL与window重新枚举并留证；`scenario.py`会抛出JS异常，None／按钮已点击不算业务成功。原生确认必须截图核对正确窗口，不能盲发Return。截图CGWindowID与AppleScript窗口ID不一定同一，Chrome用CoreGraphics先映射。
- Worker上限保留10；已核验10个注册且TTL有效的上传Worker，并有本任务实际消费记录。空闲心跳间隔可能约480秒，不能以120秒阈值误判上限只有1个。

## 后续科学裁定沿用

见user-scientific-adjudications.json及原对话：LaH9@50仅Cc、保留Fig1c冲突不拆卡；PrH9@100两组Tc0人工裁定、F-43m；CeH10@200 Tc/DOS Fm-3m；ScH10@300仅P63/mmc结构不录Cmcm；LaH10@200 EPC软件共用QE方法推断注明限制。图谱返修目标High-throughput Study on Rare-earth Clathrate Hydride High-temperature Superconductors；材料级返修优先ScH6@300从错误Im-3m改P63/mmc/194/hexagonal（仅草稿确实错误才使用）。若新草稿已正确不能故意改坏，需再核验真实修改项。五阶段排障轮完成后才留证清理重新上传；当前不能删稿重置。

## 记忆

本会话使用MEMORY.md:30-34，rollout 01a1c333-83b4-7420-9d64-765fd5cbee81；最终如引用该背景，附一块规范记忆引用。不更新全局记忆。
