## 提交前补充

其他任务的v4轴标定与#224每轮5次后暂停改动已经各自提交，当前仅本轮source_handoff与记录差异，不将它们重复纳入本任务。真实后续使用当前本机源码，v4将重新处理v3图源，输入PDF/任务不变。

## 最新：补源真实验证完成，待提交后网页继续

用户确认CeH10 Tc/DOS为Fm-3m的答复仍有效。上游scope_sources真实正确页码重提完成：30 Claim有效/未读0，全部原数值不变；CeH10初猜不再借R-3m，先为空。正式组装未恢复错误；单候选隔离重放原Fm-3m规划提案通过，原跨相保护代码未改。相同输入复用。相邻CeH9也去除初猜借相；10项几何优化从原Methods补为classical_static，adjacent-fields.json明确列出。64相关回归及仅本补丁独立HEAD投影64、四宿主233、字段契约、12变异通过。

隔离81873已结束，live-output-final.txt/verification.json等通过，勿重复启动。第一次辅助页码误写的中止尝试不计通过，正确脚本现从_source读18—28。当前源码已补读图升级后旧块与当前原页的上下文定位兼容，不用旧派生值，tests覆盖。

有其他任务未提交改动：chart_calibration/chart_reading及图表测试/Spec227（v4）、model_runtime/Spec224（5次暂停重试）等，别纳入本任务提交、别回滚。Overview有这两任务hunk，仅追加的scope_source段落是本任务。upload_jobs.py/extraction_sources.py/test_extraction_source_handoff.py本轮改动均本任务。

实际业务任务尚未重新继续，仍failed/phase_inventory、Job6dc44e55...，29/29 coverage通过但未送审，无正式PaperID。下一步提交当前通过补丁/记录→Safari7839同任务正常继续。共享读图v4会重新读取v3图源；记录实际版本，不复制隔离结果进业务缓存，不关闭跨物相保护。新版本旧块定位已覆盖。Chrome隔离1758018018，操作前按URL重新确认。

## 最新：用户已确认，正在上游修正（覆盖下面待答复旧记录）

用户明确答复“Tc/DOS采用Fm-3m，由我确认”。已逐字追加#211 Spec，结论仅本篇CeH10@200GPa Tc/DOS，R-3m声子原文独立保留，不等同两种物相。无需再问这项科学选择。

技术选择保持state_inventory.py跨相保护不变，从上游补齐缺失依据重提：extraction_sources新增inventory_scope_sources，仅用规划冲突定位相同材料/压力、当前窗口确实拥有记录的遗漏原文；把原始结构表/方法块及原页传给extractor，规划答案/用户结论不进模型依据。原始SI2(18—28页)错误借R-3m，图S33源p26是目标；补p2/3方法、p33表S1等原块+5张原页。源/记录值不直接改，其他窗口不失效，后面规划保护仍须过。

这部分正在修改，尚未提交：backend/ingest/extraction_sources.py、upload_jobs.py、test_extraction_source_handoff.py、docs/specs/211.../spec.md及本轮记录。63项相关回归、Node24四宿主233、字段契约、12变异已通过。真实隔离重提正在运行：exec session81873（如已结束用输出/进程判定），脚本runs/20261110-peng2017-phase/verify_live.py，stdout live-output-final.txt，runtime live/state.json，当前接收模型输出。不要重复启动同请求。

第一次隔离辅助脚本把窗口摘要页写成22，原实际18—28；已仅SIGINT停止自己进程54918，原请求/部分输出保留并helper-correction.json明确不算通过。正确脚本从原_source读取18—28，当前运行正确。原PDF图像/块页码从未改。等本正确运行完成→验证CeH10phase为Fm-3m或留空且不借声子相、来源/数值/同输入复用→测试保存重读/下游→文档自动提交→Safari正常继续同一任务。勿手改缓存/DB或关闭相保护。

实际业务任务仍failed/summarizing，Job6dc44e55...，29/29/正文SI coverage均complete；原问题phaseplanning尚未越过，未送审/无PaperID，五阶段2—5未执行。Chrome隔离窗口1758018018、Safari7839沿下文，操作前按URL重新枚举核验；勿动14881另窗口。

## 最新状态优先（2026-11-10）

Job6dc44e55实际29/29、正文/SI coverage全部complete，来源交接已在真实任务通过。随后material_state_inventory失败：state-24 CeH10 200GPa初始R-3m，规划拟改Fm-3m。实际SI24页FigS31声子R-3m、SI33页TableS1结构Fm-3m；标量图4/S33未直接标相。原始SI DOS候选借用声子相，规划按结构试图改相，原保护正确拦截。真实输入/响应固定重放仍失败且输入不变。

已发异步问题请用户科学/处理方案决定，并展示phase-source-comparison.png：推荐Tc/DOS物相待确认、结构/声子分别留来源，并让初始未审核归属进入既有核对；第二选项是用户明确Tc/DOS采用Fm-3m。尚未收到答复，绝不能把默认推荐当批准，不实施依赖方案。旧跨物相保护不放宽，未送审/正式PaperID为空。手动填写按钮代码会清空草稿，未点击它。新证据runs/20261110-peng2017-phase/；真实OCR来源通过证据在20261110-peng2017-ocr/actual-*。

# Peng2017真实黑盒续接

完整五阶段未完成，仍在阶段1，未送审、无正式Paper ID。用户持续授权保留同任务02b23f7c5e524f8ba718f48d92a07f75，不清理、不重传、不手改库。最新Job6dc44e55-8591-4de5-a688-720963001c69，先运行observe.py确认最新状态，不沿旧快照操作。

503已恢复；上一Job c85abbe6完成29/29段后，正文4页因OCR的NH10而coverage失败。实际PDF与保存的Marker同区域原块都是YH10。按#136旧FR006/007/017补齐必要冲突交接，已本地提交9b6381d9：失败续跑只为unreadable原块附同页同位置备选原块和SHA验证原页，原OCR/原IR不改；新模型重提完整窗口，严格来源/科学契约保持。完整IR校验原引用，coverage只计选中主干；错引句/外来源仍拒绝。相同输入复用；无无限科学纠错或材料字典。

原PDF新模型隔离验证通过：36 Claim有效/未读0，YH10 400GPa λ2.41、YH9 150GPa λ4.42，μ*=.1/.13；ScH6 300GPa约100/90K、ScH9 400GPa约180/170K及λ约1.3/1.4保留；LaH10 200GPa 288K、λ空。原OCR和Marker证据同时保留。未写业务稿。新增6项在内64通过；11旧失败独立HEAD同样失败（传输1/旧实验字段8/旧解析夹具2），单列。Node24四宿主233、字段契约、12变异通过。证据runs/20261110-peng2017-ocr/，verification.json、原失败gzip、live请求/结果及verify_live.py。第二次复验是同一真实请求完整缓存复用，非新模型调用。

已正常从Safari点击继续新Job6dc44e55，当前论文级新来源检查点处理，无错误；新版本#673等改了论文级源过滤，因此该阶段重新建立检查点。正文/SI的v3图表先前完成38/31点，文件身份未改。不要仅因隔离通过或ready宣布黑盒完成。后续仍需实际解析→字段核对/谱/引用→网页送审→真实退回→返修重提→具体日志批准→探索YH10并按实际分组所有权核验正式库。

Safari用户窗口7839；任务URL http://127.0.0.1:5173/upload/tasks/02b23f7c5e524f8ba718f48d92a07f75；同窗口/account刚核验myth620137018@163.com/用户。另一个窗口14881也打开本任务，勿操作它（可能用户/其他测试在观察）。原Chrome隔离窗口已关闭，已创建新隔离窗口1758018018，/account实际核验mayuan_mark@163.com/超级管理员，origin http://localhost:5173。该浏览器当前模型标签deepseek1/deepseek-v4-pro，未修改；上传任务仍server:LLM2/gpt-6.1-sol。勿动Chrome旧1758017519或1208论文。每次act先枚举实际URL，不沿标签序号；act(...window=实际id)。

operate.py在本目录，先import它后可from scenario import call_browser。真实网页操作所有业务，不调用业务API/SQL改值。textContent已标明仅DOM采集，实际控件读value；全页innerText曾超时。observe.py与verify_formal.py只读，须PYTHONPATH=.、Python=/Users/mayuan/software/miniconda3/envs/sc-wiki/bin/python，先load_dotenv(.env)而不读密钥。正式库最近absent。源PDF本目录../20261106-peng2017/sources/，哈希/角色/大小见case-grobid-fix.json和active-task.json，DOI10.1103/PhysRevLett.119.107001，标题Hydrogen Clathrate Structures in Rare Earth Hydrides at High Pressures: Possible Route to Room-Temperature Superconductivity，检索YH10。

分支mayuan；每次写入和提交前核验。9b6381d9提交后工作区曾干净，其他#226/#228—230任务此前已各自提交，别回滚。新改动仅本轮记录；自动多行本地提交，不push/部署其他环境。Worker配置10，热重载旧实例可使注册13，实际本任务仅1个upload busy/queue0（另有news Job），别杀busy。

主报告tests/TestForRealScenario/Peng2017-20261106-result.md。#136已评论issuecomment-6759223253记录本轮修复，#227仍OPEN且SC005未完成。继续工具推进，分析简短。
