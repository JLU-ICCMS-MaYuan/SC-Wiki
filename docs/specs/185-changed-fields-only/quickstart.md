# 验收入口：只覆盖实际变化

1. 使用项目运行环境，固定隔离数据，不写用户草稿或业务库。
2. 执行本功能故障先失败与保存／重读／权限边界测试。
3. 四类宿主执行npm run test:form-contract --prefix frontend及npm run test:form-contract:mutation --prefix frontend，并完成受影响回归。
4. 涉及来源时分别保留固定重放与真实PDF定向提取证据；冻结版本与工作稿不得混用。
5. 真实结果记录到validation.md，保留未完成项，精确提交本任务，不推送部署。
