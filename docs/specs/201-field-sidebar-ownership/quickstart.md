# 验证步骤

使用项目Conda环境Node，依次执行：

```sh
npm run test:upload-ui --prefix frontend -- tests/01_decentralized_uploading/field-sidebar-ownership.test.tsx
npm run test:form-contract --prefix frontend
npm run test:form-contract:mutation --prefix frontend
npm run build --prefix frontend
```

字段提示规则及相关历史已迁移至 [#220](../220-field-red-marking/spec.md)，本处不再独立定义。
