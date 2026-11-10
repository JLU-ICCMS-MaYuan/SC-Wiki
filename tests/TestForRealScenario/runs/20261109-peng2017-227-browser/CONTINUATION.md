# Peng2017真实黑盒续接

完整五阶段未完成，仍在阶段1，未送审、无正式Paper ID。用户持续授权保留同任务02b23f7c5e524f8ba718f48d92a07f75，不清理、不重传、不手改库。最新Job6dc44e55-8591-4de5-a688-720963001c69，先运行observe.py确认最新状态，不沿旧快照操作。

503已恢复；上一Job c85abbe6完成29/29段后，正文4页因OCR的NH10而coverage失败。实际PDF与保存的Marker同区域原块都是YH10。按#136旧FR006/007/017补齐必要冲突交接，已本地提交9b6381d9：失败续跑只为unreadable原块附同页同位置备选原块和SHA验证原页，原OCR/原IR不改；新模型重提完整窗口，严格来源/科学契约保持。完整IR校验原引用，coverage只计选中主干；错引句/外来源仍拒绝。相同输入复用；无无限科学纠错或材料字典。

原PDF新模型隔离验证通过：36 Claim有效/未读0，YH10 400GPa λ2.41、YH9 150GPa λ4.42，μ*=.1/.13；ScH6 300GPa约100/90K、ScH9 400GPa约180/170K及λ约1.3/1.4保留；LaH10 200GPa 288K、λ空。原OCR和Marker证据同时保留。未写业务稿。新增6项在内64通过；11旧失败独立HEAD同样失败（传输1/旧实验字段8/旧解析夹具2），单列。Node24四宿主233、字段契约、12变异通过。证据runs/20261110-peng2017-ocr/，verification.json、原失败gzip、live请求/结果及verify_live.py。第二次复验是同一真实请求完整缓存复用，非新模型调用。

已正常从Safari点击继续新Job6dc44e55，当前论文级新来源检查点处理，无错误；新版本#673等改了论文级源过滤，因此该阶段重新建立检查点。正文/SI的v3图表先前完成38/31点，文件身份未改。不要仅因隔离通过或ready宣布黑盒完成。后续仍需实际解析→字段核对/谱/引用→网页送审→真实退回→返修重提→具体日志批准→探索YH10并按实际分组所有权核验正式库。

Safari用户窗口7839；任务URL http://127.0.0.1:5173/upload/tasks/02b23f7c5e524f8ba718f48d92a07f75；同窗口/account刚核验myth620137018@163.com/用户。另一个窗口14881也打开本任务，勿操作它（可能用户/其他测试在观察）。原Chrome隔离窗口已关闭，已创建新隔离窗口1758018018，/account实际核验mayuan_mark@163.com/超级管理员，origin http://localhost:5173。该浏览器当前模型标签deepseek1/deepseek-v4-pro，未修改；上传任务仍server:LLM2/gpt-6.1-sol。勿动Chrome旧1758017519或1208论文。每次act先枚举实际URL，不沿标签序号；act(...window=实际id)。

operate.py在本目录，先import它后可from scenario import call_browser。真实网页操作所有业务，不调用业务API/SQL改值。textContent已标明仅DOM采集，实际控件读value；全页innerText曾超时。observe.py与verify_formal.py只读，须PYTHONPATH=.、Python=/Users/mayuan/software/miniconda3/envs/sc-wiki/bin/python，先load_dotenv(.env)而不读密钥。正式库最近absent。源PDF本目录../20261106-peng2017/sources/，哈希/角色/大小见case-grobid-fix.json和active-task.json，DOI10.1103/PhysRevLett.119.107001，标题Hydrogen Clathrate Structures in Rare Earth Hydrides at High Pressures: Possible Route to Room-Temperature Superconductivity，检索YH10。

分支mayuan；每次写入和提交前核验。9b6381d9提交后工作区曾干净，其他#226/#228—230任务此前已各自提交，别回滚。新改动仅本轮记录；自动多行本地提交，不push/部署其他环境。Worker配置10，热重载旧实例可使注册13，实际本任务仅1个upload busy/queue0（另有news Job），别杀busy。

主报告tests/TestForRealScenario/Peng2017-20261106-result.md。#136已评论issuecomment-6759223253记录本轮修复，#227仍OPEN且SC005未完成。继续工具推进，分析简短。
