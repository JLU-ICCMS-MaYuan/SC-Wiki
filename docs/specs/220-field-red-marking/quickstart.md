# 验收步骤

1. 四宿主分别加载原通过和原免审字段，真实输入新值，检查红框、侧栏与计数；同值与未改空项保持，普通保存不消红。
2. 已有问题开始核对仍留红；当前合法结果解除后更新，旧结果迟到不得清除新修改。多子项只解决一个不整体消红。
3. 人工资料保存及定位的具体操作按 [#221](../221-scientific-field-sidebar/spec.md) 验收；颜色只按本单元的当前有效事实判断。
4. 验证固定隔离草稿的无关渲染、值读取、DOM 扫描、请求及输入延迟。原用户返修稿只读，不作为写入测试对象。
5. 执行 npm run test:field-contract --prefix frontend、npm run test:form-contract --prefix frontend、npm run test:form-contract:mutation --prefix frontend、受影响回归及 npm run build --prefix frontend。
6. 检查迁移原文摘要、旧处引用、标准字段契约未改；本地提交后不自行推送。

## 本轮增量

新增 FR-011—014／SC-006—008 尚待实施：补充任务完成与科学通过的区别、未通过／技术失败矩阵、资料再次变化及迟到结果保护；具体核对界面只引用 #221，不以旧163项测试宣称新增交互已经通过。
