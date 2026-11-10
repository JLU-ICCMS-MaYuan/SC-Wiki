# 本机验收

1. 在mayuan分支安装固定LangMem依赖，不修改模型/并发配置。
2. 执行backend/tests/test_model_runtime.py与test_model_memory.py，记录修复前失败与修复后通过；阻塞请求停止、重复继续、旧代次回写及原图关联必须覆盖。
3. 运行npm run test:field-contract --prefix frontend、test:form-contract、test:form-contract:mutation及受影响既有测试和构建。
4. Safari原用户打开Peng2017同任务，观察唯一动态，停止后重读、继续；Chrome超管保持独立窗口。不能用API替代送审/拒绝/批准。
5. 原正文/SI从来源重新调用受影响模型步骤，保留失败、复用与重跑范围。完整五阶段记录tests/TestForRealScenario/Peng2017-20261106-result.md。

连续5次临时失败自动暂停后，在原任务查看最后错误及请求ID；确认服务恢复后手动“继续解析”，本轮最多5次，已完成响应直接复用。该上限只约束传输故障，不表示科学字段验收完成。
