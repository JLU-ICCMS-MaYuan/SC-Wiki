# 验证步骤

使用项目Conda环境Node，依次执行：

```sh
npm run test:upload-ui --prefix frontend -- tests/01_decentralized_uploading/field-sidebar-ownership.test.tsx
npm run test:form-contract --prefix frontend
npm run test:form-contract:mutation --prefix frontend
npm run build --prefix frontend
```

固定五项重放及四宿主：打开超导模块，所属字段标红；从字段进入侧栏选择名称/值/类型/单位，逐项理由不同，切换不发模型或写请求；设置修改后未应用不能切走。只读可查看，删除重排不串位；计算条件标题可打开关系项。实际结果见validation.md，未执行的检查不得视为通过。
