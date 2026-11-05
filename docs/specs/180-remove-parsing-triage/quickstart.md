# 验收方式

使用 `python3 -m scripts.local_deploy.environment` 返回的项目运行环境；Node 22 执行前端检查。

1. 运行 `npm run test:form-contract --prefix frontend` 与 `npm run test:form-contract:mutation --prefix frontend`。
2. 运行撤回分类的完整宿主回归、#109 来源展示、#177 单字段、声子方法、Tc 配对及年份回归。
3. 用隔离 Worker 与草稿存取验证原文和备选文本仍存在，新数据不生成 triage；旧字段不触发入口或重建。
4. 在仅包含本次补丁的候选中重复必要检查并构建，排除并行未提交改动依赖。

科学字段右侧栏功能设计、原话及历史已迁移至 [#221](../221-scientific-field-sidebar/spec.md)，本处不再独立维护。
具体命令、数量和限制以 [验收记录](validation.md) 为准；不将静态删除或 Mock HTTP 写入写成业务环境验收。
