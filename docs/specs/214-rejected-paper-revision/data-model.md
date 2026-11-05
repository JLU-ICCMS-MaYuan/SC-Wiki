# 数据模型：统一拒绝返修流程，保持旧批准版公开

## 2026-11-05 当前状态投影

不新增表或修改科学契约。检查列表返回的workflow_status由最新正式交接派生，无交接时回退papers.review_status；checked_status保留本人上次决定，仅用于历史。当前pending稿先从已检查查询移除，再计数和分页；已拒绝筛选按workflow_status判断。论文ID和不可变历史事件保持，不为重新送审创建第二条跟踪记录。

## 权威对象

papers的批准状态和当前科学图决定公开版；最新handoff.holder仅派生私有workflow_status；PaperRevisionDraft/ScientificReviewDraft持有工作稿，正式快照不可变。

## 不变量

沿用review-commit，在论文行锁内执行拒绝交接并建立作者返修稿；私有列表批量投影交接头，SQL用MAX事件ID定位，公开查询不引入无关私有读取；批准事务才替换公开图。

## 迁移与持久化边界

本项沿用现有实体和标准字段，不新增数据库结构或科学键；本轮拆分不更改任何数据。完整原实现及源文件哈希见[证据清单](assets/evidence.json)。
