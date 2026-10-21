# 实施与验收记录

日期：2026-10-21。本次授权范围的修复与本地验收完成；远程链接和部署验收尚未完成，Issue保持OPEN。

## 已实现

- evidence_proposals：合法可空字段与value_kind启用槽分别校验，SSCHA空单位和N(EF)文本记录不再因未使用数值槽拒绝保存；非法类型/身份改写继续拒绝。规则通过的paper_inference原样接受不伪造人工确认，prepare/finalize保留规则证据。
- condition_rules：v2条件策略不包含Tc结果数字；SSCHA非谐流程及材料/物相仍有原文约束。结果归属独立在Tc结果核对，不反向撤销共用条件。
- condition_lifecycle：对已知v1/v2完整旧claim、相同来源和必要依赖重验原文后输出新投影；保留历史与失败尝试，真实新冲突撤回支持。新版组内承载结果切换及依赖数组索引有界规范化，不能跨组借用。
- scientific_evidence：读取与同版本保存复用上述规则，失败尝试不覆盖唯一有效凭证；来源/科学值/范围真实变化继续失效并提供具体原因。

## 验证与制品

1. 初始11个新回归中7个失败，复现四类物性原样保存、空槽、SSCHA空单位及Tc依赖；修复后通过。
2. 当前工作区相关6份回归曾113项通过；最终独立HEAD仅叠加本次增量，6份112项通过（同期其他任务新增测试未混入）。独立候选位于/private/tmp/scwiki144-candidate，基线与增量文件清单位于/tmp/scwiki144-implementation-baseline。
3. 真实MySQL外层事务回滚：本次6项及既有条件核对4项，共10项通过，覆盖上传/返修/管理员接受与finalize、N(EF)名称草稿、同版本失败保留唯一证据和冲突撤回。
4. 完整浏览器实际路由/upload/tasks/...、完整UploadTaskEditor与来源侧栏，HTTP/登录身份为隔离适配，后端服务函数与MySQL回滚存储真实执行。使用真实草稿副本重建331/0.1起点，新增296/0.16；初始、新增、自动保存、刷新、完成、200 GPa失败重试、N(EF)名称保存、重新核对漏引并增加删除首点即时/保存后检查，共10个检查点通过。5次草稿持久化、2次核对保存，零pageerror，未提交/批准论文。不是实际登录生产HTTP端到端。
5. 浏览器制品在.data/issue144-validation/browser-results.json与browser-final.png；原始过程留/tmp/scwiki144-browser。最终自动保存前后scrollY均4726，焦点保持μ*；侧栏完成返回位置差小于5像素。早先一次回顶部由测试脚本点击页顶立即保存造成，去掉该操作后自动保存位置稳定，不能把测试动作误报为产品根因。
6. 当前真实草稿只读核查145项条件全部supported；SSCHA与N(EF)原样值保存校验无错误，无科学值写回，无新增人工确认。详见.data/issue144-validation/current-verification.json。

## 独立源码验证的边界

工作区在本任务开始前已有来源角色识别等未提交改动；这些改动不属于#144且未纳入提交。独立HEAD使用旧来源读取路径直接读取当前任务时，3项真实来源接受测试不能复用当前工作区生成的来源摘要；这是来源读取版本不一致，未绕过来源hash校验。改用当前实际来源的只读固定快照（source-snapshot.json及SHA-256）后，独立源码的保存/原文重验/数据库合同测试10项通过。该重放不覆盖来源读取入口；工作区完整浏览器验收使用当前真实来源读取。

独立回归命令：JWT_SECRET_KEY=测试专用值，项目Python运行pytest的test_review_lifecycle.py、test_evidence_proposals.py、test_condition_auto_review.py、test_association_recheck.py、test_scientific_evidence.py、test_property_evidence.py。

MySQL重放：SCWIKI_CURRENT_MYSQL=1、SCWIKI_SOURCE_SNAPSHOT指向只读来源快照，加载本地.env后运行test_review_lifecycle_mysql.py和test_condition_auto_review_mysql.py。当前工作区也可用SCWIKI_SOURCE_TASK指定原任务，所有写入仍仅限随机测试目标且回滚。

浏览器：SCWIKI_CURRENT_MYSQL=1、SCWIKI_SOURCE_TASK指定原任务，PYTHON_BIN/PLAYWRIGHT_MODULE/CHROMIUM_PATH指向本地依赖，node运行tests/01_decentralized_uploading/review-lifecycle-browser.mjs。用户原草稿未写入；仅测试副本删除已有250 GPa第二点以重建新增起点。

## 前端授权与最终验证

用户明确回复“允许修复这部分逻辑，界面保持原样”后，仅修改evidenceFields.ts与EvidenceWorkflow.tsx的字段定位/失效判断。共用字段按稳定group_key找到新承载记录并更新定位路径；Tc/μ*本身仍按原结果身份，跨组不得借用。父级变更通知依据实际字段变化处理，不能直接将所有子项置stale。没有布局、样式或按钮改动。

独立HEAD候选61项前端回归与TypeScript编译通过；最初删除首点回归失败，修复后通过。完整页面新增/自动保存保持scrollY=4726与μ*焦点，侧栏完成恢复位置；删除首点即时和持久化重读后8项SSCHA条件均不误红。重排、跨组与真实软件变化反例由前端回归覆盖。

浏览器首次200 GPa失败重试场景曾在上一轮自动保存尚未完成时点击完成，得到“当前编辑尚未保存成功”；输入保留。最终脚本等待已有保存完成后测试503注入与显式重试，恢复成功；未新增并发保存排队功能。

## 尚未覆盖
- 用户原始视频未取得可读取文件；原报告其他跳动入口未定位，不能宣称所有跳动均已修复。
- 未做新的完整PDF上传解析、生产部署或远程Spec/附件链接验收；不推送、不关闭Issue。
