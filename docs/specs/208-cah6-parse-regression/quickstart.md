# 核对现有记录与重新验证入口

## 只读核对本次结果

1. 阅读[验收记录](validation.md)及[精简报告](../176-scientific-form-filling/assets/full-reparse-20261103.json)，核对任务、模型、来源SHA-256、14个业务源码摘要和实际结果。
2. 查看[首页截图](../176-scientific-form-filling/assets/full-reparse-form-20261103.png)与[Tc分组截图](../176-scientific-form-filling/assets/full-reparse-tc-20261103.png)。截图证明当时页面，不代替当前现场查询。
3. 使用`git show b1fc93be`检查实施内容；本轮文档补档不代表再次完成PDF模型调用。
4. 原始制品和失败试跑位于原记录说明的本机`.data/`目录，不把原PDF、凭据、SQL备份或完整用户草稿提交到Git。

## 按已有入口验证

实际重跑需重新确认当次目标和数据操作范围，不能从本记录推断可以再次删除所有解析稿。不要对已交出或用户新编辑的任务盲目执行历史脚本。

不改变运行数据的表单回归入口：

```bash
npm run test:field-contract --prefix frontend
npm run test:form-contract --prefix frontend
npm run test:form-contract:mutation --prefix frontend
```

针对已授权、未提交且ready的任务，可使用现有完整入库回滚工具：

```bash
python scripts/verify-upload-submit.py \
  --task TASK_ID \
  --output /tmp/scwiki-submit-verification \
  --allow-model-results --review-cycle
```

`TASK_ID`为实际明确选择的任务，不把固定历史任务编号当成永久有效对象。脚本使用已配置本机环境；输出包含原文和来源，应保存在受控本机目录。验收查看`model_calls=0`、`formal_blocked=[]`、两种批准角色、引用保留和`original_preserved=true`；外层数据库回滚不等于已正式送审。

## 预期与限制

字段提示规则及相关历史已迁移至 [#220](../220-field-red-marking/spec.md)，本处不再独立定义。
