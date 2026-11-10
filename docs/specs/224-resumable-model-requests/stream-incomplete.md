# 模型流结束但没有正常完成原因

## 真实失败

Y-H任务d789acceee124022b3257f84780d1156，Job4fbb0c76-4fee-45a9-8936-5ac2d44eebba，在26/29时，SI第32—34页的一次提取返回4367字符，结束在row_index字段名中间。调用账本finish_reason=None、JSONDecodeError；旧程序将其包装成严格结构错误，立即终止。

原始响应与调用目录a841dc4b55a420d7ae0e53d82323bc6049c6cc08975c134bc7f63aac6826f6f7-0仍留存，固定夹具backend/tests/fixtures/model_stream_incomplete/failure.json没有修补半截内容。没有原始HTTP逐帧抓包，不能断言具体哪层断开或是否收到DONE；这里只确认SDK流结束、没有正常完成原因且内容未闭合。不是503、上下文超限或科学字段错误。

## 依据及修复

#224 FR-002/005及此前部分输出停滞超时修复36951348已经规定传输失败保留原响应、恢复原请求、完整输出才能进入科学校验。本次恢复该职责，不增加科学纠错轮次，不改5次预算或字段契约。

上传持久执行的Chat Completions流结束后、JSON/原生工具处理前检查finish_reason；已经输出但无正常完成原因时抛出ModelIncompleteStreamError（httpx.RemoteProtocolError），显示LLM_STREAM_INCOMPLETE，既有运行器保留半截并整体重发原请求。正常stop的非法JSON/额外字段，以及明确length/content_filter继续立即停止。无输出路径、其他宿主兼容及并行#233的Responses适配不在本补丁变更范围内。

## 验证分层

- 最终固定夹具在独立HEAD先3失败/4通过，证明能检出半截JSON被误当结构错误、缺完成原因的完整JSON被错误采用及错误的恢复预算。
- 7项新真实SDK/SSE边界、运行器/记忆/JSON/分片及LLM共56项在共享工作区通过，纯HEAD加本次2生产文件及回归的独立投影也56通过。原请求逐字相同，不拼接部分内容；连续5次断流实际暂停且不发送第6次，完整错误结构仅请求1次。
- 初次投影全复制llm.py时夹入并行#233的新Responses适配却缺其新依赖，22项失败；已保存该失败，并按本次hunk单独重建，不混入提交或计为产品通过。
- 原失败窗口采用同一server:LLM2/gpt-6.1-sol及已核验的相同端点/输入/schema重新调用，一次成功，经过正式严格schema和JSON保存重读。没有回填业务候选或重写科学值；生产仍需网页继续。
- 四宿主233项、12项变异、字段契约v1和Python编译通过。没有依赖变更；Bandit当前环境缺模块未执行，不声明扫描通过。

代码采用只含本次hunk的索引快照；共享#232—235取图、反馈、原生工具与其他功能改动保持原样。Issue及远程Spec仍按原状态，不自动推送或关闭。

证据：tests/TestForRealScenario/runs/20261110-peng2017-workflow-debug-01/issues/stream-incomplete/。原失败、独立基线、共享/投影回归、真实模型和网页业务分别记录。当前仍阶段一，26个完整分段保留；尚无正式论文ID，送审/拒绝/返修/批准/探索与最终无调试复测均未完成。
