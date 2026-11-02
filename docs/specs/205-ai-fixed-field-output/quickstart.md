# 验证步骤

1. 使用项目Conda Python执行定向schema/LLM调用测试，验证新增键与伪造人工扩展先失败。
2. 用当前LLM2流式接口执行对抗请求及非法schema，记录请求形状、返回、模型和耗时，不记录密钥或端点。
3. 从同哈希CaH6补充PDF/IR重新提取相关字段并走正式后处理；在隔离副本保存重读，原任务不写入。
4. 执行test:field-contract、test:form-contract、test:form-contract:mutation及受影响Python回归。已有失败独立基线记录。
5. 核对仅本次暂存增量，更新Issue/Overview并提交；不推送。
