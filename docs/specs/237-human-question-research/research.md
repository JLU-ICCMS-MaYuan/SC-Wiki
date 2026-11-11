# 调研与设计取舍：归档解析人工问答的Codex与开源机制调研依据

参见[规格](spec.md)与[计划](plan.md)。以下均为AI查证/工程理解，用户原话保存在规格中。

## 已核对的公开实现

核对日期为2026-11-11；Codex证据固定到提交`5228d94a27b7f84cae4854acbb5ea3b3e90dfeaf`。官方文档站本轮访问返回403，以下结论来自OpenAI官方GitHub仓库；没有声称核实全部桌面端内部代码。

| 来源 | 已核对行为 | 适用边界 |
| --- | --- | --- |
| [同步工具](https://github.com/openai/codex/blob/5228d94a27b7f84cae4854acbb5ea3b3e90dfeaf/codex-rs/core/src/tools/handlers/request_user_input.rs#L78-L94) | 调用session.request_user_input并等待返回 | 不是SC-Wiki的无阻塞字段调度 |
| [异步工具](https://github.com/openai/codex/blob/5228d94a27b7f84cae4854acbb5ea3b3e90dfeaf/codex-rs/core/src/tools/handlers/request_user_input_async.rs#L131-L148) | 发送带questions的Async消息，立即返回accepted | 只说明模型能继续，不证明依赖字段已暂挂 |
| [终端问题状态](https://github.com/openai/codex/blob/5228d94a27b7f84cae4854acbb5ea3b3e90dfeaf/codex-rs/tui/src/bottom_pane/async_questions/state.rs#L14-L54) | 追加、按消息ID去重、每题独立输入草稿 | 首项预选不等于提交；SC-Wiki另定义三类入口 |
| [跟进消息测试](https://github.com/openai/codex/blob/5228d94a27b7f84cae4854acbb5ea3b3e90dfeaf/codex-rs/tui/src/chatwidget/tests/questions_tests.rs#L115-L153) | 普通新用户消息可清空终端待答队列 | 不能照搬；本需求未答问题必须保留 |

## 开源取舍

| 项目与来源 | 可借鉴点 | 许可证核对及限制 |
| --- | --- | --- |
| [Codex](https://github.com/openai/codex/blob/main/LICENSE) | 异步问题消息、追加去重与自由填写 | Apache-2.0；本次只参考设计，未复制代码 |
| [LangGraph interrupt实现](https://github.com/langchain-ai/langgraph/blob/main/libs/langgraph/langgraph/types.py) | 中断值、检查点、Command(resume) | MIT；节点恢复可能重新执行，不能认为函数后半段自动无副作用继续 |
| [LangChain人工中间件](https://github.com/langchain-ai/langchain/blob/master/libs/langchain_v1/langchain/agents/middleware/human_in_the_loop.py) | approve/edit/reject/respond及按动作触发 | MIT；工具执行批准不等于SC-Wiki科学字段审核 |
| [AutoGen异步人工示例](https://github.com/microsoft/autogen/tree/main/python/samples/core_async_human_in_the_loop) | 人工输入及暂停恢复 | [LICENSE-CODE](https://github.com/microsoft/autogen/blob/main/LICENSE-CODE)为MIT；[根LICENSE](https://github.com/microsoft/autogen/blob/main/LICENSE)为CC-BY-4.0，代码与文档必须区分。纠正先前口头表格笼统写整个项目CC-BY-4.0的说法 |
| [CrewAI](https://github.com/crewAIInc/crewAI) | 顺序任务、人工输入和检查点思路 | MIT；本轮只读README，未验证其运行语义，不据此选作依赖 |

除固定Codex提交外，其余为本轮读取的main/master路径，可能漂移；将来若复制代码必须固定实际提交并保留所需声明。本轮不安装、运行或比较这些框架的性能，不声称任何项目已在SC-Wiki验证。

## 采用决策

借鉴Codex问题协议、LangGraph恢复原则和LangChain决定结构，以本仓库轻量模块实现。完整框架会引入另一套任务、图状态和存储；当前已有RQ、SQL工作稿与Redis，不以框架替换实现本需求。同步等待整篇和默认关闭/重复解析对照均未采用。
