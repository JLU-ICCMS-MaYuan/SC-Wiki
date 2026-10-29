# 验收入口

1. 项目运行环境由 python3 -m scripts.local_deploy.environment 返回；使用该环境的Python与Node22。
2. 运行物理方法作用域、结构优化和计算方法回归，验证旧响应确能检出污染；保留科学值和原始来源。
3. 运行 npm run test:form-contract --prefix frontend 与 npm run test:form-contract:mutation --prefix frontend；四类完整宿主验证新字段、来源、无变化保存及失败恢复。
4. 在隔离副本重提原PDF受影响字段并正式保存重读；不写原用户草稿，不复用旧答案。不具备真实调用时T005保留未完成。
5. 独立候选构建及迁移/存取验证后提交本任务。全部实际命令、结果及边界记录到validation.md；远程文档链接未经推送访问核验不关闭Issue。
