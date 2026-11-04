# 验收步骤

1. 四宿主分别加载原通过和原免审字段，真实输入新值，检查红框、侧栏与计数；同值与未改空项保持，普通保存不消红。
2. 已有问题开始核对仍留红；当前合法结果解除后更新，旧结果迟到不得清除新修改。多子项只解决一个不整体消红。
3. 在所属侧栏填写未保存说明并关闭，该字段有提醒；提交定位到该字段，旧值草稿继续保留。
4. 验证固定隔离草稿的无关渲染、值读取、DOM 扫描、请求及输入延迟。原用户返修稿只读，不作为写入测试对象。
5. 执行 npm run test:field-contract --prefix frontend、npm run test:form-contract --prefix frontend、npm run test:form-contract:mutation --prefix frontend、受影响回归及 npm run build --prefix frontend。
6. 检查迁移原文摘要、旧处引用、标准字段契约未改；本地提交后不自行推送。
