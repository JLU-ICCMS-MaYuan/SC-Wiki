# Y-H文献通用流程黑盒

最新用户要求以tests/TestForRealScenario/document-upload-blackbox-workflow.md执行：先完整排障五阶段，再留证按精确ID清理该轮表单/正式论文/解析数据，原文件新上传无调试五阶段通过后才结束，最终轮保留正式论文。旧历史保留current-task要求已由这次新流程更新。

开始前已按明确授权备份并后台仅清理02b23f7c5e524f8ba718f48d92a07f75，paused/无正式PaperID；其余三历史task已不存在不操作。归档previous-task-evidence.tar.gz含5616成员/204038350字节，backup/cleanup manifest及result证明原文件和3篇独立正式论文保留。归档本地保留，不放Git大二进制。

当前尚无新Task，旧02不可恢复。Safari7839的http://127.0.0.1:5173/upload已通过正常组件装入正文+SI真实字节（attach_inputs.py执行完毕），尚未点击开始上传。不要重复attach，先读UI已选列表。Safari/account核验myth620137018@163.com用户；Chrome隔离1758018018 /account核验mayuan_mark@163.com超级管理员。每次交互按实际URL重新枚举（operate模块ROOT设本目录），不沿旧tab索引。

代码JSON请求修复已验证但正在准备提交：backend/rag/llm.py只给缺JSON提示的系统消息补句，已有合规消息字节不变；public入口在预算/归档/缓存前处理，transport幂等，json_schema/原生工具/本地固定字段校验均保留。真实旧503请求仅加JSON、同模型/输入/工具，serverLLM2/gpt-6.1-sol首尝试返回合法read_original_page native调用；未执行工具，不是整篇通过。新5回归及后端66通过/1真实隔离Redis条件跳过，四宿主233、字段契约、12变异通过。暂停测试组合导入顺序故障HEAD同组合复现，夹具显式绑定同存储已修正。未改变5次暂停规则。

依赖安全扫描非全通过：锁/清单无变更，前端6项（4低2中），本机后端14包108条通告；Bandit1个旧LOW assert和HEAD相同。无依赖升级；安全审查security-review.json。官方文档HTTP403未获取，不伪称已读；官方SDK实际类型和实际请求序列化已检。

用户明确图谱标题返修目标：High-throughput Study on Rare-earth Clathrate Hydride High-temperature Superconductors（仅knowledge_graph_title，不是文献title）。材料返修依据用户最新确认：Fm-3m YH10/CeH10/LaH10、P63/mmc YH9/CeH9都是笼型结构，用现有structure_families。新草稿原值正确不能造改，需选具体真实待改状态。CeH10@200GPa Tc/DOS采用Fm-3m已由用户确认，R-3m声子来源独立保留。未授权添加新科学键。

输入case.json仅本轮数据，正文/SI原路径在../20261106-peng2017/sources，哈希角色不变，DOI10.1103/PhysRevLett.119.107001、检索YH10。当前case记录phases全部未执行。下一步完成本轮源码/证据自动多行本地提交（不push）→核验当前上传文件/邮箱/模型→网页开始上传→记录新Task/Job/角色哈希→完整五阶段，故障留证调查修复后当前步骤续跑，不能每修一次删稿。当前排障轮完整通过后才跨轮清理与最后新上传无调试。

分支mayuan，写入/提交前核验。当前工作区只有本轮rag/llm.py、JSON新测试、暂停测试夹具及对应205/224/Overview/报告文档；不要纳入不属于本任务的后续共享改动。运行代码需Python=/Users/mayuan/software/miniconda3/envs/sc-wiki/bin/python、PYTHONPATH=.，load_dotenv但不读/记录任何凭据。模型和所有业务通过真实Safari/Chrome，不API/SQL代办；只读调查和明确清理例外允许。旧run的observe.py仍指02，不要直接用它观察新任务。
