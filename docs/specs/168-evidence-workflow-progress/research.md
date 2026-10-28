# 技术研究
- 决策：保留原同步科学准备路径，附带短期进度标识并轮询。理由：截图等待发生在submit-check返回任务之前；仅修改LinearProgress无法获得真实准备进展。备选：迁移全部准备到RQ会改变请求上下文、失败及调度职责，本次不采用。
- 决策：状态按用户与随机请求ID隔离，取消使用墓碑及原子更新。理由：取消可能早于请求注册，必须阻止迟到响应重新推进或排队。
- 决策：完成组数映射20–95，完成响应经过最终版本检查后才100。理由：原worker先更新批次再持久化、get_job还执行版本校验，批次全完成不能提前宣称流程成功。
- 决策：只展示完成步骤与已用时间，不估算剩余时间。来源：已确认Spec。
- 证据：EvidenceWorkflow.gate/execute、evidence.submit_check/create_job/get_job、property_evidence.run_evidence_job。
