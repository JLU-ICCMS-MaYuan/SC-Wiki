# 数据模型：统一拒绝返修流程，保持旧批准版公开

## 权威对象

papers的批准状态和当前科学图决定公开版；最新handoff.holder仅派生私有workflow_status；PaperRevisionDraft/ScientificReviewDraft持有工作稿，正式快照不可变。

## 不变量

沿用review-commit，在论文行锁内执行拒绝交接并建立作者返修稿；私有列表批量投影交接头，SQL用MAX事件ID定位，公开查询不引入无关私有读取；批准事务才替换公开图。

## 迁移与持久化边界

本项沿用现有实体和标准字段，不新增数据库结构或科学键；本轮拆分不更改任何数据。完整原实现及源文件哈希见[证据清单](assets/evidence.json)。
