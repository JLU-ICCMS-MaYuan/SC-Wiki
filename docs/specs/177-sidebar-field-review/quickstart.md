# 验证入口

使用项目 sc-wiki Python；运行本次字段接口／存储回归、前端字段保存与核对回归，以及：

```sh
npm run test:form-contract --prefix frontend
npm run test:form-contract:mutation --prefix frontend
npm run build --prefix frontend
```

真实 MySQL 使用外层事务回滚及随机临时目标，不修改用户草稿。全宿主验证自动保存最新人工依据、单字段排队、全局通知不误拦截、真正当前字段／依据变化拒绝、遮罩编辑锁、结果重开及提交复用。实际结果写入 validation.md，不以静态字符串检查代替交互。
